ルールをPythonスクリプトで定義する
==================================

..
   対象読者：パラメータを使ったタスクとコマンドルールの書き方がわかっている人
   目標：独自のルールを定義できるようになる

これまで、各タスクのルールにはシェルスクリプトを記述していました。
本章では、このルールをPythonの関数で定義する方法を学びます。
これにより、シェルスクリプトで簡単に書けないような処理を各タスクで行うことができ、実験の幅が大きく広がります。

単純な例
---------

まず感覚を掴んでもらうため、シェルスクリプトでもできることを関数で書くとどのようになるか、を説明します。

以下は一番最初の :ref:`first-wscript`  で紹介したwscriptの一部です。

.. code-block:: python

   import maf

   def configure(conf):
       pass

   def build(exp):
       exp(target='message', rule='echo "Hello" > ${TGT}')

これと同じことを、関数ルールを用いて書こうとすると、以下のようになります。

.. code-block:: python

   import maf
   import maflib.util    # 1

   @maflib.util.rule     # 2
   def my_echo(task):
       task.outputs[0].write('Hello')

   def configure(conf):
       pass

   def build(exp):
       exp(target='message', rule=my_echo)  # 3

変更した点をまとめると、

(1) 関数を定義するためのライブラリの読み込み
(2) 関数の定義
(3) ``rule`` に、定義した関数を指定

となります。ルールを定義する場合、上のように、

.. code-block:: python

   @maflib.util.rule
   def function_name(task):
       # 実際の処理を記述

という部分は、こうするという決まりです。こうやって定義しておくと、

.. code-block:: python

   exp(target='...', rule=function_name)

などと、exp呼び出しの際に ``rule`` に関数名を指定することで、この関数が実行されるようになります。

タスクオブジェクト
------------------

定義した関数の中身を詳しく見ていきます。

.. code-block:: python

   @maflib.util.rule
   def my_echo(task):
       task.outputs[0].write('Hello')

``my_echo`` が実行される際、この実行は、引数である ``task`` というオブジェクトを通して行われます。
このオブジェクトはタスクオブジェクトと呼ばれます。
これは、そのタスクに固有の情報を全て保持しています。
例えば、上の ``task.outputs`` はそのタスクの出力ノードの情報を保持します。
後で紹介するように、タスクに紐づいたパラメータにアクセスしたい場合、 ``task.parameter`` でアクセスができます。

``task.outputs[0]`` は、出力ノードを指します。
今回の例では ``exp(target='message', ...)`` と記述したように出力のメタノードは一種類ですが、 ``task.output`` 自体はリストなので、最初の要素を指定するために ``[0]`` と指定しなければいけません。
ここではノードオブジェクトの ``write()`` 関数を使っています。
これは、引数で与えた文字列をノードに書き出す関数で、つまり、先ほどの ``echo`` と全く同じことをしていることになります。

最初の ``@maflib.util.rule`` デコレータについては説明を省略します。
これは独自のルールを定義する際に必要なものだと覚えておいてください。

実際の使用例
--------------

先ほどの例はほぼ実用性はありませんが、関数ルールが具体的にどのような場面で役に立つかを紹介します。
基本的にこれは、シェルで一行で書くことができない処理、もしくはできるけれど、pythonで書いた方が簡単な処理を行いたい場合に利用するものです。

クイックスタートで用いた例を再掲します。

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
               'C': [0.001, 0.01, 0.1, 1]}),
           rule='liblinear-train -s ${s} -c ${C} ${SRC} ${TGT} > /dev/null')
    
       exp(source='news20.t.scale model',
           target='accuracy',
           rule='liblinear-predict ${SRC} /dev/null > ${TGT}')

       exp(source='accuracy',
           target='accuracy.json',
           rule=maflib.rules.convert_libsvm_accuracy)

       exp(source='accuracy.json',
           target='accuracy.png',
           for_each='',
           rule=maflib.plot.plot_line(
               x = {'key': 'C', 'scale': 'log'},
               y = 'accuracy',
               legend = {'key': 's'}))

ここで用いている :py:func:`maflib.rules.convert_libsvm_accuracy` が、関数ルールの使用例です。
二つ目のexp呼び出しまでで得られた ``accuracy`` メタノードの各ノードは、次のように、LIBSVM の標準出力を保持しています。

.. code-block:: sh

   $ ./cat build/accuracy/0-accuracy
   Accuracy = 88.99% (8899/10000)

``maflib.rules.convert_libsvm_accuracy`` は、これらをjsonに変換します。

.. code-block:: sh

   $ ./cat build/accuracy.json/0-accuracy.json
   {"accuracy": 88.99}

これは次のように実装されています。

.. code-block:: python

   @maflib.util.rule
   def convert_libsvm_accuracy(task):
       content = task.inputs[0].read()           # ノードの read() メソッドで中身をstringで得る
       j = {'accuracy': float(content.split(' ')[2][:-1])}  # 数値の部分を取り出してdictionaryに変換
       task.outputs[0].write(json.dumps(j))      # json.dumps() でjsonに変換し、書き出す

こういった文字列処理などをシェルのコマンドで実現するのは大変なので、関数ルールが便利です。

パラメータとsubprocess
------------------------

別の例として、関数の中でこれまでのようなコマンド呼び出しを行う例を紹介します。

上のLIBLINEARを例にとって、例えば、設定毎に訓練にかかった時間を計測したいとします。
この場合は、最初のexp呼び出しを次のように書き換えればOKです。

.. code-block:: python

   @maflib.util.rule
   def train_with_time(task):
       import time, subprocess
       begin = time.time()        # 開始時刻

       cmd = 'liblinear-train -s {s} -c {C} {src} {tgt} > /dev/null'.format(
           s = task.parameter['s'],             # タスクのパラメータはこのように辞書形式でアクセスできる
           C = task.parameter['C'],
           src = task.inputs[0].abspath(),
           tgt = task.outputs[0].abspath())
    
       subprocess.check_call(cmd, shell = True) # 関数内でのコマンド呼び出しにはsubprocessを使う

       sec = time.time() - begin # 終了時刻から時間を計測

       task.outputs[1].write(str(sec)) # それを二番目の出力ノードに書き出す

   def build(exp):
       exp(source='news20.scale',
       target='model train_time', # train_time という出力ノードを追加
       parameters=maflib.util.product({
           's': [0, 1, 2, 3],
           'C': [0.001, 0.01, 0.1, 1]}),
       rule=train_with_time)  # コマンドの代わりに関数を呼び出す

       ...

ここでは ``target`` を二種類に増やしています。
またこれまで ``rule='liblinear_train ...'`` とコマンドを記述していた部分の処理が、関数 ``train_with_time`` に置き換わっています。

ここでは、シェルのコマンドの実行時間を、関数内で計測しているので、関数内部でコマンドを呼び出さないといけません。
このような場合は、 python の `subprocess <http://docs.python.jp/2/library/subprocess.html>`_ モジュールなどを使って、自分でコマンドを呼び出さないといけません。
ここで使っている ``subprocess.check_call()`` は、引数のコマンドを実行します。
その際 ``shell = True`` を与えておかないと、このようにコマンドを一つの文字列で指定することができないので、注意して下さい。

タスクパラメータ
-----------------

最後に、タスクに固有の定数を外部から与える方法を紹介します。

ここではまた前に戻って、簡単なechoを関数で置き換える例を取り上げます。
以下の二つのタスク定義で、異なるのは ``Hello`` か ``Hi`` かだけなので、これを抽象化したいとしましょう。

.. code-block:: python

   def build(exp):
       exp(target='message', rule='echo "Hello" > ${TGT}')
       exp(target='message2', rule='echo "Hi" > ${TGT}')

この際、同じことを次のように書くことができます。

.. code-block:: python

   @maflib.util.rule
   def my_echo(task):
       task.outputs[0].write(task.parameter['msg'])

   def build(exp):
       exp(target='message', rule=my_echo(msg='Hello'))
       exp(target='message', rule=my_echo(msg='Hi'))

このように、 ``rule`` の関数指定に、引数でキーと値を指定すると、それらが関数内で ``parameter`` として使えるようになります。

これを使うと、例えば関数内で使われる定数を外部から与えることが可能になります。

.. code-block:: python

   @maflib.util.rule
   def train_with_time(task):
       ...
       
       cmd = 'liblinear-train -s {s} -c {C} -B {B} {src} {tgt} > /dev/null'.format(
           s = task.parameter['s'],
           C = task.parameter['C'],
           B = task.parameter['B'], # 'B' の値を追加。これは定数で与える。
           src = task.inputs[0].abspath(),
           tgt = task.outputs[0].abspath())
    
       subprocess.check_call(cmd, shell = True)       
       ...

   def build(exp):
       exp(source='news20.scale',
       target='model train_time',
       parameters=maflib.util.product({
           's': [0, 1, 2, 3],
           'C': [0.001, 0.01, 0.1, 1]}),
       rule=train_with_time(B = 0))

       ...

ここで ``B`` の値は関数の中で変化しない定数です。
このようなタスク固有の定数を与える際には、この機能が役に立ちます。

以下は少し補足的な内容です。このような方法ではなく、 ``parameters`` の中に一種類の値を指定してはダメなのかと思われるかもしれませんが、これには別の問題が発生します。

.. code-block:: python

   # 以下のコードは非推薦
   def build(exp):
       exp(source='news20.scale',
           target='model train_time',
           parameters=maflib.util.product({
               's': [0, 1, 2, 3],
               'C': [0.001, 0.01, 0.1, 1],
               'B': [0]}), # Bは一種類だけなので、定数の役割を果たす。
           rule=train_with_time)

       ...

この方法の問題点として、 ``B`` というパラメータが以降のタスクで使えなくなってしまいます。
:ref:`meta-node-to-parameterized-task` で述べたように、複数のタスクで同じ種類のパラメータを定義した場合、それらに食い違いが発生すると、タスクが実行されません。
このように発生する問題を防ぐために、mafの書き方として、先に述べたように **タスクに定数を指定する場合は、呼び出し時に指定する** ことを推薦しています。

maflib.rules
---------------

:py:mod:`maflib.rules` モジュールには、いくつかの便利な関数が実装済みなので、参考にして下さい。
例えば :py:func:`maflib.rules.download` は、指定したURLからファイルをダウンロードして使えるようにします。

.. code-block:: python

   def build(exp):
       exp(target='news20.scale',
           rule=maflib.rules.download(
                url='http://www.csie.ntu.edu.tw/~cjlin/libsvmtools/datasets/multiclass/news20.scale.bz2',
                decompresss_as='bz2'))  # 省略した場合、解凍を行わない

このように、 ``url`` でダウンロード先のURLを、 ``decompress_as`` で解凍方法を指定できます。
この後のタスクでは、 ``source='news20.scale'`` とすると、解凍したファイルを入力ノードに指定することができるようになります。

まとめ
--------

本章では maf の機能のうち、以下の項目を紹介しました。

- 関数ルールの定義の仕方と呼び出し方
- 関数内でのタスクオブジェクトの使い方

  - ``inputs, outputs, parameters`` の呼び出し
  - subprocessを使ったコマンド実行
  
- タスクパラメータによる定数の指定法

ルールを関数で定義することで、コマンドでは表せないような複雑な処理を実験の中に組み込むことができます。
本章では、簡単なタスクを自分で定義する方法を紹介しましたが、次章では、集約タスクを自分で定義する方法を扱います。
