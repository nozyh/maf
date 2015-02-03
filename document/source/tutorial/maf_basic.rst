簡単な実験を maf 上で書く
=========================

- 対象読者：maf クイックスタートを読み終えた人
- 目標：コマンドによる単純なファイル処理を maf 上で書けるようになる

この章では、maf をつかった簡単なファイル処理を通して、maf の基本的な概念を学びます。

実験内容
--------

maf の動かし方がわかりやすいように、ここでは実験とは呼べないようなごく単純なファイル処理を行います。
まず適当な文字列を ``message`` と ``message2`` というファイルに書き出します。
これらを一つのディレクトリにまとめたり、つなげたりしたファイルを出力するのが目標です。

この処理を maf で行うために、次のような ``wscript`` ファイルを書きます（ものぐさな人はコピー、時間のある方は写経しましょう）。

.. code-block:: python

   import maf

   def configure(conf):
       pass

   def build(exp):
       exp(target='message', rule='echo "Hello" > ${TGT}')
       exp(target='message2', rule='echo "Hi" > ${TGT}')

       exp(source=['message', 'message2'],
           target='message_box/',
           rule='''
           cp ${SRC[0].abspath()} ${TGT}
           cp ${SRC[1].abspath()} ${TGT}
           ''')

       exp(source='message_box', target='all_messages',
           rule='cat ${SRC}/* > ${TGT}')

クイックスタートにも書きましたが、この ``wscript`` と同じディレクトリに ``waf`` や ``maf.py`` を配置して、次のコマンドを実行します。

.. code-block:: sh

   $ ./waf configure
   Setting top to                           : /data-old/home/beam2d/github/pfi/maf/exp
   Setting out to                           : /data-old/home/beam2d/github/pfi/maf/exp/build
   'configure' finished successfully (0.001s)

これで実験の準備ができました。
実験を実行するには、同じディレクトリで次のコマンドを実行します。

.. code-block:: sh

   $ ./waf build

``./waf`` コマンドは、このようにサブコマンドを受け付けます。
特に実験を行う ``build`` サブコマンドはもっともよく使うため、省略できるのでした。

.. code-block:: sh

   $ ./waf
   Waf: Entering directory `/data-old/home/beam2d/github/pfi/maf/exp/build'
   [2/4] message:  -> build/message
   [2/4] message2:  -> build/message2
   [3/4] message_box: build/message build/message2 -> build/message_box
   [4/4] all_messages: build/message_box -> build/all_messages
   Waf: Leaving directory `/data-old/home/beam2d/github/pfi/maf/exp/build'
   'build' finished successfully (0.022s)

すぐに実行し終わるはずです。
実行結果は ``build`` ディレクトリに出力されます。
最終的なディレクトリ構成は以下のようになります（以下は ``tree`` コマンドの結果で、``.`` からはじまる隠しファイルは省略しています）。

::

   .
   ├── build
   │   ├── all_messages
   │   ├── c4che
   │   │   ├── _cache.py
   │   │   └── build.config.py
   │   ├── config.log
   │   ├── message
   │   ├── message2
   │   └── message_box
   │       ├── message
   │       └── message2
   ├── maf.py
   ├── maf.pyc
   ├── waf
   └── wscript

``build/c4che`` ディレクトリは waf が内部的に使うもので、 ``build/config.log`` は ``./waf configure`` コマンドのログです。
これらは実験結果とは関係ありません。
``build`` 以下のそのほかのファイルやディレクトリが、上の wscript をもとに生成された実験結果です。

wscript の基本
--------------

wscript の基本的な構成からおさらいします。

.. code-block:: python

   import maf  # (1)

   def configure(conf):  # (2)
       pass

   def build(exp):  # (3)
       ...

(1) ``import maf`` で maf がロードされます。
    これを書くと何が起きるかは、このチュートリアルでは詳しく説明しませんが、maf を使う場合には必ずこれを書きましょう。
(2) ``configure`` 関数は ``./waf configure`` コマンドの実行時に呼び出されます。
    この関数の使い方はチュートリアルの後半で扱います。
    しばらく必要ありませんが、定義しないと ``./waf configure`` 実行時にエラーが発生します。
    ですので、ひとまず空の関数として定義しておきます。
(3) ``build`` 関数は ``./waf build`` コマンドの実行時に呼び出されます。
    ここに実験の本体を書きます。

``build`` 関数の引数には **コンテキストオブジェクト** が渡されます。
maf では、この引数によく ``exp`` という名前を使いますが、ほかの名前を使うこともできます。
以降、このチュートリアルでは ``exp`` という変数名は必ずコンテキストオブジェクトを表すことにします。

exp の関数呼び出し
------------------

コンテキストオブジェクト ``exp`` は関数のように振る舞います。
関数呼び出しによって、一つの **タスク** が生成されます。
一つのタスクは、一つのシェルスクリプトを実行します。
このシェルスクリプトは **ルール** と呼ばれ、 ``rule`` 引数に与えます。
シェルスクリプトへの入力と出力は、それぞれ ``source`` と ``target`` という引数に指定します。

まとめると、 ``exp`` は以下の引数をとります。

:source: 入力ファイル名、またはそのリスト（省略可能）
:target: 出力ファイル名、またはそのリスト
:rule: ルール（シェルスクリプト [1]_ ）

``source`` や ``target`` に空白区切りの文字列を与えた場合、空白で区切ってリストのように扱われます。
つまり、 ``A`` と ``B`` という 2 つのファイルを指定したい場合、 ``['A', 'B']`` と指定するのと ``'A B'`` と指定するのは同じ意味です。

入力ファイルが必要ないタスクの場合、 ``source`` を省略できます。
タスクは必ずなにかを出力しないといけない（そうでないと実行する意味がない）ので、 ``target`` は省略できません。

ルールにはシェルスクリプトを書くことができます。
ここで、ルール文字列内では ``${式}`` という書き方で文字列展開ができます。
この式のなかでは ``SRC`` と ``TGT`` という変数が使えます。

:SRC: 入力ファイルリスト（ノードリスト）
:TGT: 出力ファイルリスト（ノードリスト）

これらはリストですが、その要素は文字列ではなくて **ノード** と呼ばれるオブジェクトです。
ノードオブジェクトの関数として、 ``abspath`` 関数だけ覚えておきましょう。

*abspath()*
   ノードがさすファイルへの絶対パスを返します。

ノードリストを ``${SRC}`` や ``${TGT}`` のように展開すると、各ファイルの絶対パスを空白文字でつなげたものに展開されます。
N 番目のファイルへのパスだけを展開したい場合、 ``abspath`` 関数をつかって ``${SRC[N].abspath()}`` や ``${TGT[N].abspath()}`` のように書きます。

冒頭の wscript に戻って、最初の 2 つのタスクを見てみましょう。

.. code-block:: python

   exp(target='message', rule='echo "Hello" > ${TGT}')
   exp(target='message2', rule='echo "Hi" > ${TGT}')

これらは、Hello や Hi とだけ書かれたファイルを生成しています。
入力は必要ないので、入力ノード ``source`` は指定していません。
出力ノードにはここで好きな名前をつけます。
重要なことは、 **これらの出力ファイルは実際には ``build`` ディレクトリのなかに作られる** ということです。
wscript 内で ``message`` と書いていても、実体は ``build/message`` にあります。

本章の例では扱いませんでしたが、あらかじめ用意したファイルを入力に使うこともできます。
この場合、入力ファイルは ``build`` ディレクトリではなく、 ``waf`` ファイルが置かれたディレクトリ以下に置きます。

ディレクトリノード
------------------

TODO

.. [1] ルールを Python 関数で与えることもできます。
       その方法はチュートリアルの中盤で説明します。
