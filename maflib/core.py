# TODO(beam2d): Add a simple documentation at the top.
# TODO(beam2d): Decide which license to use and add its description.

import collections
import copy
import os
import os.path
import types
import inspect
try:
    import cPickle as pickle
except ImportError:
    import pickle

import waflib.Build
import waflib.Utils
from waflib.TaskGen import before_method, feature

# TODO(beam2d): Add tests.

def options(opt):
    pass


def configure(conf):
    pass


class ExperimentContext(waflib.Build.BuildContext):
    """Context class of waf experiment (a.k.a. maf)."""

    cmd = 'experiment'
    fun = 'experiment'
    variant = 'experiment'

    def __init__(self, **kw):
        super(ExperimentContext, self).__init__(**kw)
        self._experiment_graph = ExperimentGraph()

        # Callback registered by BuildContext.add_pre_fun is called right after
        # all wscripts are executed.
        super(ExperimentContext, self).add_pre_fun(
            ExperimentContext._process_call_objects)

    def __call__(self, **kw):
        """Main method to generate tasks."""

        call_object = CallObject(**kw)
        self._experiment_graph.add_call_object(call_object)

    def _process_call_objects(self):
        """Callback function called right after all wscripts are executed.

        This function virtually generates all task generators under
        ExperimentContext.

        """
        # Run topological sort on dependency graph.
        call_objects = self._experiment_graph.get_sorted_call_objects()

        # TODO(beam2d): Remove this stub file name.
        self._parameter_id_generator = ParameterIdGenerator(
            'build/experiment/.maf_id_table',
            'build/experiment/.maf_id_table.tsv')
        self._nodes = collections.defaultdict(set)

        try:
            for call_object in call_objects:
                self._process_call_object(call_object)
        finally:
            self._parameter_id_generator.save()

    def _process_call_object(self, call_object):
        self._set_rule_and_dependson(call_object)        

        if hasattr(call_object, 'for_each'):
            self._generate_aggregation_tasks(call_object, 'for_each')
        elif hasattr(call_object, 'aggregate_by'):
            self._generate_aggregation_tasks(call_object, 'aggregate_by')
        else:
            self._generate_tasks(call_object)
            
    def _set_rule_and_dependson(self, call_object):
        # dependson attribute is a variable or a function, which the change is
        # automatically traced; this is set by two ways:
        #  1) write dependson attribute in wscript
        #  2) give rule in Rule object, which is set dependson values
        rule = call_object.rule
        if ('rule' in call_object.__dict__ and not isinstance(rule, str)):
            dependson = getattr(call_object, 'dependson', [])
            if isinstance(rule, types.FunctionType):
                rule = Rule(rule, dependson)
            else:
                rule.add_dependson(dependson)
            # Callable object other than function is not allowed as a rule in
            # waf. Here we relax this restriction.
            call_object.rule = lambda task: rule.fun(task)
            call_object.dependson = rule.stred_dependson()
        else:
            call_object.dependson = []
            
    def _generate_tasks(self, call_object):
        if not call_object.source:
            for parameter in call_object.parameters:
                self._generate_task(call_object, [], parameter)

        parameter_lists = []

        # Generate all valid list of parameters corresponding to source nodes.
        for node in call_object.source:
            node_params = self._nodes[node]
            if not node_params:
                # node is physical. We use empty parameter as a dummy.
                node_params = {Parameter()}

            if not parameter_lists:
                for node_param in node_params:
                    parameter_lists.append([node_param])
                continue

            new_lists = []
            for node_param in node_params:
                for parameter_list in parameter_lists:
                    if any(p.conflict_with(node_param) for p in parameter_list):
                        continue
                    new_list = list(parameter_list)
                    new_list.append(node_param)
                    new_lists.append(new_list)

            parameter_lists = new_lists

        for parameter_list in parameter_lists:
            for parameter in call_object.parameters:
                if any(p.conflict_with(parameter) for p in parameter_list):
                    continue
                self._generate_task(call_object, parameter_list, parameter)

    def _generate_task(self, call_object, source_parameter, parameter):
        # Create target parameter by merging source parameter and task-gen
        # parameter.
        target_parameter = Parameter()
        for p in source_parameter:
            target_parameter.update(p)
        target_parameter.update(parameter)

        for node in call_object.target:
            self._nodes[node].add(target_parameter)

        # Convert source/target meta nodes to physical nodes.
        physical_source = self._resolve_meta_nodes(
            call_object.source, source_parameter)
        physical_target = self._resolve_meta_nodes(
            call_object.target, target_parameter)

        # Create arguments of BuildContext.__call__.
        physical_call_object = copy.deepcopy(call_object)
        physical_call_object.source = physical_source
        physical_call_object.target = physical_target
        del physical_call_object.parameters

        self._call_super(
            physical_call_object, source_parameter, target_parameter)

    def _generate_aggregation_tasks(self, call_object, key_type):
        # In aggregation tasks, source and target must be only one (meta) node.
        # Source node must be meta node. Whether target node is meta or not is
        # automatically decided by source parameters and for_each/aggregate_by
        # keys.
        if not call_object.source or len(call_object.source) > 1:
            raise InvalidMafArgumentException(
                "'source' in aggregation must include only one meta node")
        if not call_object.target or len(call_object.target) > 1:
            raise InvalidMafArgumentException(
                "'target' in aggregation must include only one meta node")

        source_node = call_object.source[0]
        target_node = call_object.target[0]

        source_parameters = self._nodes[source_node]
        # Mapping from target parameter to list of source parameter.
        target_to_source = collections.defaultdict(set)

        for source_parameter in source_parameters:
            target_parameter = Parameter()
            if key_type == 'for_each':
                for key in call_object.for_each:
                    target_parameter[key] = source_parameter[key]
            elif key_type == 'aggregate_by':
                for key in source_parameter:
                    if key not in call_object.aggregate_by:
                        target_parameter[key] = source_parameter[key]
            target_to_source[target_parameter].add(source_parameter)

        for target_parameter in target_to_source:
            source_parameter = target_to_source[target_parameter]
            source = [self._resolve_meta_node(source_node, parameter)
                      for parameter in source_parameter]
            target = self._resolve_meta_node(target_node, target_parameter)

            self._nodes[target_node].add(target_parameter)

            # Create arguments of BuildContext.__call__.
            physical_call_object = copy.deepcopy(call_object)
            physical_call_object.source = source
            physical_call_object.target = target
            if key_type == 'for_each':
                del physical_call_object.for_each
            else:
                del physical_call_object.aggregate_by

            self._call_super(
                physical_call_object, source_parameter, target_parameter)

    def _call_super(self, call_object, source_parameter, target_parameter):
        taskgen = super(ExperimentContext, self).__call__(
            **call_object.__dict__)
        taskgen.env.source_parameter = source_parameter
        taskgen.env.update(target_parameter.to_str_valued_dict())

        depkeys = [('dependson%d' % i) for i in range(len(call_object.dependson))]
        taskgen.env.update(dict(zip(depkeys, call_object.dependson)))

        taskgen.parameter = target_parameter

    def _resolve_meta_nodes(self, nodes, parameters):
        if not isinstance(parameters, list):
            parameters = [parameters] * len(nodes)

        physical_nodes = []
        for node, parameter in zip(nodes, parameters):
            physical_nodes.append(self._resolve_meta_node(node, parameter))
        return physical_nodes

    def _resolve_meta_node(self, node, parameter):
        if parameter:
            parameter_id = self._parameter_id_generator.get_id(parameter)
            node = os.path.join(
                node, '-'.join([parameter_id, os.path.basename(node)]))
        if node[0] == '/':
            return self.root.find_resource(node)
        return self.path.find_or_declare(node)


class CyclicDependencyException(Exception):
    """Exception raised when experiment graph has a cycle."""
    pass


class InvalidMafArgumentException(Exception):
    """Exception raised when arguments of ExperimentContext.__call__ is wrong.

    """
    pass


class Parameter(dict):
    """Parameter of maf task.

    This is a dict with hash(). Be careful to use it with set(); parameter has
    hash(), but is mutable.

    """
    def __hash__(self):
        # TODO(beam2d): Should we cache this value?
        return hash(frozenset(self.iteritems()))

    def conflict_with(self, parameter):
        """Checks whether the parameter conflicts with given other parameter.

        :return: True if self conflicts with parameter, i.e. contains different
            values corresponding to same key.
        :rtype: bool

        """
        common_keys = set(self) & set(parameter)
        return any(self[key] != parameter[key] for key in common_keys)

    def to_str_valued_dict(self):
        """Gets dictionary with stringized values.

        :return: A dictionary with same key and stringized values.
        :rtype: dict of str key and str value

        """
        return dict([(k, str(self[k])) for k in self])


class Rule(object):
    """A wrapper object of a rule function with associate values,
    which change is tracked on the experiment.
    
    :param fun: target function of the task.
    :param dependson: list of variable or function, which one wants to track.
        All these variables are later converted to string values, so if
        one wants to pass the variable of user-defined class, that class
        must provide meaningful `__str__` method.
        
    """
    
    def __init__(self, fun, dependson=[]):
        self.fun = fun
        self.dependson = dependson
        self.dependson.append(self.fun)

    def add_dependson(self, dependson):
        self.dependson += dependson

    def stred_dependson(self):
        def to_str(d):
            # function type is converted to the string of the body by inspect.getsource
            if isinstance(d, types.FunctionType): return inspect.getsource(d)
            else: return str(d)
        return map(to_str, self.dependson)


class CallObject(object):
    """Object representing one call of ``ExperimentContext.__call__()``."""

    def __init__(self, **kw):
        """Initializes a call object.

        ``kw['source']`` and ``kw['target']`` are converted into list of
        strings.

        :param **kw: Arguments of ``ExperimentContext.__call__``.

        """
        self.__dict__.update(kw)

        for key in ['source', 'target', 'features']:
            _let_element_to_be_list(self.__dict__, key)

        for key in ['for_each', 'aggregate_by']:
            if hasattr(self, key):
                _let_element_to_be_list(self.__dict__, key)

        self.__dict__['features'].append('experiment')
        if 'parameters' not in self.__dict__:
            self.parameters = [Parameter()]
            """List of parameters indicated by the taskgen call."""

    def __eq__(self, other):
        return self.__dict__ == other.__dict__


class ExperimentGraph(object):
    """Bipartite graph consisting of meta node and call object node."""

    def __init__(self):
        self._edges = collections.defaultdict(set)
        self._call_objects = []

    def add_call_object(self, call_object):
        """Adds call object node, related meta nodes and edges.

        :param call_object: Call object be added.
        :type call_object: :py:class:`CallObject`

        """
        index = len(self._call_objects)
        self._call_objects.append(call_object)

        for in_node in call_object.source:
            self._edges[in_node].add(index)

        for out_node in call_object.target:
            self._edges[index].add(out_node)

    def get_sorted_call_objects(self):
        """Runs topological sort on the experiment graph.

        :return: List of call objects that topologically sorted.
        :rtype: list of :py:class:`CallObject`

        """

        nodes = self._collect_independent_nodes()
        edges = copy.deepcopy(self._edges)

        reverse_edges = collections.defaultdict(set)
        for node in edges:
            edge = edges[node]
            for tgt in edge:
                reverse_edges[tgt].add(node)

        # Topological sort
        ret = []
        while nodes:
            node = nodes.pop()
            if isinstance(node, int):
                # node is a name of call object
                ret.append(self._call_objects[node])

            edge = edges[node]
            for dst in edge:
                reverse_edges[dst].remove(node)
                if not reverse_edges[dst]:
                    nodes.add(dst)
                    del reverse_edges[dst]
            del edges[node]

        if edges:
            raise CyclicDependencyException()

        return ret

    def _collect_independent_nodes(self):
        nodes = set(self._edges)
        for node in self._edges:
            nodes -= self._edges[node]
        return nodes


class ParameterIdGenerator(object):
    """Consistent generator of physical nodes identifier corresponding to
    their parameters.

    Meta node has a path and its own parameters, each of which corresponds to
    one physical waf node named as 'path/N', where N is a unique name of the
    parameter. The correspondence between parameter and its name must be
    consistent over multiple execution of waf, so we serializes the table to
    hidden file.

    This class also dumps the correspondence to a human-readable text file.
    The file is tab-separated line for each correspondence: the first element
    is an identifier and the second is a JSON representation of the
    correspondent parameter.

    NOTE: On exception raised during task generation, save() must be called
    to avoid inconsistency on node names that had been generated before the
    exception was raised.

    """
    def __init__(self, path, text_path):
        """Initializes the generator.

        :param path: Path to persisitent file of the table.
        :type path: str
        :param text_path: Path to file that the table is dumped to as a human-
            readable.
        :type text_path: str

        """
        # TODO(beam2d): Isolate persistency support from resolver.

        self.path = path
        """Path to file that the table is serialized to."""

        self.text_path = text_path
        """Path to file that the table is dumped to as a human-readable text."""

        if os.path.exists(path):
            with open(path) as f:
                self._table = pickle.load(f)
        else:
            self._table = {}

    def save(self):
        """Serializes the table to the file at self.path."""
        with _create_file(self.path) as f:
            pickle.dump(self._table, f)

        with _create_file(self.text_path) as f:
            parameter_ids = self._table.items()
            parameter_ids.sort(key=lambda param_and_id: int(param_and_id[1]))
            for parameter, id in parameter_ids:
                f.write('%s\t%s\n' % (id, parameter))

    def get_id(self, parameter):
        """Gets the id of given parameter.

        :param parameter: Parameter object.
        :type parameter: :py:class:`Parameter`
        :return: Identifier of given parameter. The id may be generated in this
            method if necessary.
        :rtype: str

        """
        if parameter in self._table:
            return self._table[parameter]

        new_id = str(len(self._table))
        self._table[parameter] = new_id

        return new_id


class ExperimentTask(waflib.Task.Task):
    """A task class specific for ExperimentContext.

    The purpose of this class is to bring the parameter as an attribute.
    The base class (:py:class:`waflib.Task.Task`) doesn't bring attributes
    except ``env``, but the env must be a string-valued dictionary, which is
    problematic when we want to use the parameter in an object as it is. For
    example, a float value once converted to string lose some information.

    Another motivation for this task is to control the hash value of a task:
    It is calculated based on the env, in which key is registered in ``vars``
    or ``dep_vars``. In ``__init__``, this task registers necessary keys to
    dep_vars.

    """
    def __init__(self, env, generator):
        """Initializes the task.

        :param env: Environmental variables.
        :param generator: Generator function.

        """

        super(ExperimentTask, self).__init__(env=env, generator=generator)

        self.parameter = generator.parameter
        """Parameter whose values are not stringized."""

        if not hasattr(self, 'dep_vars'): self.dep_vars = []
        self.dep_vars += self.parameter.keys()
        self.dep_vars += filter(lambda k: k.startswith("dependson"), env.keys())

@feature('experiment')
@before_method('process_rule')
def register_experiment_task_with_rule(self):
    """A task_gen method called before process_rule.

    WARNING: This method currently strongly connected to the internal of
    ``process_rule`` method, which is defined in :py:class:`waflib.TaskGen`, so
    may require a modification in future version of waf.

    The role of this method is to create ``self.bld.cache_rule_attr``, which
    is later used in ``process_rule``. It is a dictionary of ``(task_name, the
    rule of task)`` pair to a task class. This task class is a derived class of
    :py:class:`ExperimentTask` defined above, which override the run method of
    it with the function given by rule attribute written in wscript. This
    process is necessary because the ``process_rule`` cannot create a user-
    defined :py:class:`Task` with a user-defined rule (as in our case).

    In the current implementation of ``process_rule``, the ``cache_rule_attr``
    is used as follows;

    .. code-block:: py

        try:
            cache = self.bld.cache_rule_attr
        except AttributeError:
            cache = self.bld.cache_rule_attr = {}

        cls = None
        if getattr(self, 'cache_rule', 'True'):
            try:
                cls = cache[(name, self.rule)]
            except KeyError:
                pass
        if not cls:
            cls = Task.task_factory(name, self.rule,
            ....

    This snippet search for a task from cache_rule_attr dictionary first,
    so we set that dictionary beforehand.

    """
    self.name = str(getattr(self, 'name', None) or self.target or getattr(self.rule, '__name__', self.rule))
    params = {}
    if isinstance(self.rule, str):
        params['run_str'] = self.rule
    else:
        params['run'] = self.rule

    # define ExperimentTask with a user-defined rule (string or function)
    cls = type(waflib.Task.Task)(self.name, (ExperimentTask,), params)
    waflib.Task.classes[self.name] = cls
    
    self.bld.cache_rule_attr = {(self.name, self.rule):cls}


def _create_file(path):
    """Opens file in write mode. It also creates intermediate directories if
    necessary.

    """
    prefixes = []
    cur_dir = path
    while cur_dir:
        cur_dir = os.path.dirname(cur_dir)
        prefixes.append(cur_dir)
    prefixes.reverse()

    for prefix in prefixes:
        if prefix and not os.path.exists(prefix):
            os.mkdir(prefix)

    return open(path, 'w')


def _get_list_from_kw(kw, key):
    if key in kw:
        return waflib.Utils.to_list(kw[key])
    return []


def _let_element_to_be_list(d, key):
    if key not in d:
        d[key] = []
    if isinstance(d[key], str):
        d[key] = waflib.Utils.to_list(d[key])