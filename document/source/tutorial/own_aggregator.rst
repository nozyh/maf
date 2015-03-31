集約処理を自分で書く
====================

..
   対象読者：関数ルールの書き方を分かっている人
   目標：集約処理の関数を定義できるようになる

前章ではルールをPythonの関数として定義する方法を紹介しましたが、集約を行う処理を自分で定義する方法については説明していませんでした。
ここでは自分で集約処理を行うルールを書く方法を見ていきましょう。

集約タスクの例
----------------

集約タスクを定義すること自体は、ほとんど通常のタスクと同じように行うことができます。
最初はまたあまり意味のない例から始めましょう。

.. code-block:: python

   @maflib.util.rule
   def combine(task):
       for node in task.inputs: # task.inputs は集約された入力ノードのリスト
           task.outputs[0].write(node.read(), 'a')

   def build(exp):
       exp(target='number',
           parameters=maflib.util.product({'n': [0, 1, 2]}),
           rule='echo n=${n} > ${TGT}')

       exp(source='number',
           target='combined',
           for_each='',         # 集約タスクであることを知らせるために for_each が必要
           rule=combine)

この wscript を実行すると、以下の結果が得られます。

.. code-block:: sh

   ./waf
   Waf: Entering directory ...
   [1/4] 0-number:  -> build/number/0-number
   [2/4] 2-number:  -> build/number/2-number
   [3/4] 1-number:  -> build/number/1-number
   [4/4] combined: build/number/2-number build/number/1-number build/number/0-number -> build/combined
   $ cat build/combined
   n=2
   n=1
   n=0

最初のルールにより、 ``n`` の値が異なる ``number`` メタノードが作られます。
そして、この各ノードが、次のルールにより集約されています。
二番目のルールには  ``for_each=''`` がありますが、これを書くことにより、このルールが集約タスクのルールであると判断されます。
これは代わりに ``aggregate_by='n'`` としても同じです。

集約タスクのタスクオブジェクト ``task`` は、通常のタスクオブジェクトと似たように扱うことができますが、いくつか注意点があります。

(1) ``task.inputs`` は ``source`` で指定したメタノードを集約した後の、ノードのリストを返します。
    この例では、 ``n`` の値の異なる三つのノードからなるリストを返します。
(2) ``task.parameter`` は ``for_each`` で指定したパラメータの現在の値を辞書形式で返します。
    この場合は空の辞書です。
(3) ``task.source_parameters`` は集約タスク固有のフィールドで、 ``task.inputs`` と組になっています。
    現在 ``task.inputs == [2-number, 1-number, 0-number]`` となっていますが、このとき ``task.source_parameters == [{'n': 2}, {'n': 1}, {'n': 0}]`` となります。
    つまり、各ノードが対応するパラメータを、リスト形式で保持します。

これらのフィールドを扱うことにより、原理的には、複数のパラメータの組み合わせを束ねる集約タスクを自由に定義することができます。
集約タスクに関するもう一つの注意は、入力ノードは一つのみである、という点です。
これは、 ``task.inputs`` の各要素が、同じメタノードの異なるパラメータのノードである、ということからくる制限です。

@maflib.util.jason_aggregator
--------------------------------

maf では、上のように生で集約タスクを書く代わりに、特定の集約タスクを書きやすくするための仕組みが存在します。
以下では、その中の代表的な二つである二つのデコレータである、 ``json_aggregator`` と ``aggregator`` を紹介します。

``json_aggregator`` は、 :py:func:`maflib.rules.min` や :py:func:`maflib.rules.max` など、 maf に用意された多くのルールで使われています。
これは、複数の json の結果を集約して、一つの json にまとめる際に便利なデコレータです。

何が便利になるのかを見るために、まずは ``max()`` と動作と、それを上で紹介した生の集約タスクとして定義するとどうなるか、を説明します。

以下はクイックスタートで用いた ``wscript`` を少し修正したものです。

.. code-block:: python

   import maf
   import maflib.util
   import maflib.plot

   def configure(conf): pass

   def build(exp):
       exp(source='news20.scale',
           target='model',
           parameters=maflib.util.product({
               's': [0, 1, 2, 3],
               'C': [0.001, 0.01, 0.1, 1],
               'B': [-1, 1]}),     # バイアス項を追加
           rule='liblinear-train -s ${s} -c ${C} -B ${B} ${SRC} ${TGT} > /dev/null')
    
       exp(source='news20.t.scale model',
           target='accuracy',
           rule='liblinear-predict ${SRC} /dev/null > ${TGT}')

       exp(source='accuracy',
           target='accuracy.json',
           rule=maflib.rules.convert_libsvm_accuracy)

       exp(source='accuracy.json',
           target='max_accuracy.json',
           aggregate_by='B',
           rule=maflib.rules.max(key='accuracy'))

       exp(source='max_accuracy.json',
          target='accuracy.png',
          for_each='',
          rule=maflib.plot.plot_line(
              x = {'key': 'C', 'scale': 'log'},
              y = 'accuracy',
              legend = {'key': 's'}))


@maflib.util.aggregator
--------------------------




