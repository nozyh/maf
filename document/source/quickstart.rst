クイックスタート
----------------

maf は機械学習の実験管理などをやりやすくするためのツールです。ここでは maf の基本的な使い方を具体例を通して紹介します。

インストール
~~~~~~~~~~~~

maf では実験を一つのディレクトリの中で行うことを想定しています。
まずはどこかのディレクトリに移動しましょう。

.. code-block:: sh

   $ mkdir experiment && cd experiment

mafを動かすためには、 ``waf`` および ``maf.py`` という二つのpythonスクリプトが必要です。
これらは実験を行う各ディレクトリ毎に配置するのが良いでしょう。
これらは以下のコマンドでダウンロードできます。

.. code-block:: sh

   $ wget https://github.com/pfi/maf/raw/master/waf && wget https://github.com/pfi/maf/raw/master/maf.py && chmod +x waf

mafでは実験の手順を ``wscript`` というファイルに記述していきます。
以下は実験ではないですが、 ``wscript`` の書き方の簡単な例です。

.. code-block:: sh

   $ cat wscript
   import maf
   
   def configure(conf): pass
   
   def build(exp):
       exp(target='output',
           rule='echo hoge > ${TGT}')
   
   $ ./waf configure           # wscriptに書いたconfigureが実行される。実験を始める前に必要。
   Setting top to                           : /.../experiment 
   Setting out to                           : /.../experiment/build 
   'configure' finished successfully (0.004s)
   $ ./waf build               # wscriptに書いたbuildの手順が実行される。
   Waf: Entering directory `/.../experiment/build'
   [1/1] output:  -> build/output
   Waf: Leaving directory `/.../experiment/build'
   'build' finished successfully (0.016s)
   $ cat build/output
   hoge

``wscript`` 自体もpythonのスクリプトとなっていて、これが ``waf`` を実行することで読み込まれます。
最初のコマンド ``configure`` はとりあえず気にする必要はありませんが、実験を行う前に実行する必要があります。
次の ``build`` がメインの実行で、 ``wscript`` に書いた ``build`` 関数を実行します。
この例では、ここに書いた ``rule`` 内の ``${TGT}`` が自動で置き換えられた、以下のコマンドが実行されます。

.. code-block:: sh
                
   $ echo hoge > build/output

この ``${TGT}`` の対応が、 ``target`` 変数で指定されています。
maf では実験途中のモデルや結果を繋げて処理を行っていきますが、このように結果は全て自動的に ``build`` ディレクトリ以下に作られます。

実際の実験例
~~~~~~~~~~~~

mafで実験がやりやすくなることを実感してもらうために、もう少し具体的な例を紹介します。
mafが特に役に立つのは、様々なパラメータや手法に関する試行錯誤を行わないといけない場面です。
簡単な例として、ここでは `LIBLINEAR <http://www.csie.ntu.edu.tw/~cjlin/liblinear/>`_ を使用し、このパラメータのチューニングを行う場面を考えます。
mafを使えば、図1のような特定のパラメータを変化させた場合の性能の変化や、図2のような訓練データ量に対する性能の変化といった結果を、20行程度の ``wscript`` を書くことで得ることができます。

.. _size_vs_accuracy:
.. figure:: figures/size_vs_accuracy.png
   :scale: 40%

.. code-block:: python
                
   import maf
   import maflib.util
   import maflib.plot

   def configure(conf): pass

   def build(exp):
       exp(source='mnist.scale',
           target='model',
           parameters=maflib.util.product({
               's': [0, 1, 2, 3],
               'C': [0.001, 0.01, 0.1, 1, 10]}),
           rule='liblinear-train -s ${s} -c ${C} ${SRC} ${TGT} > /dev/null')
    
       exp(source='mnist.scale.t model',
           target='accuracy',
           rule='liblinear-predict ${SRC} /dev/null > ${TGT}')

       exp(source='accuracy',
           target='accuracy.json',
           rule=maflib.rules.convert_libsvm_accuracy)

    exp(source='accuracy.json',
        target='accuracy.png',
        for_each='',
        rule=maflib.plot.plot_line(
            x={'key': 'C', 'scale': 'log'},
            y='accuracy',
            legend={'key': 's'}))



