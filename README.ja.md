# ゲーム画像アセット検証, WISA 2026

[English](README.md), [Korean](README.ko.md), [Japanese](README.ja.md)

**WISA 2026: 筆頭著者、ポスター発表**

[第27回 World Conference on Information Security Applications](https://wisa.or.kr/)

2026.08.26 ~ 28, 韓国・済州、MAISON GLAD

## 手法と結果の概要

ゲーム画像50点、変換17種、対照条件5種の記録として、C2PA検証1,150件とハッシュ評価4,400行を提供します。20%クロップのTop-1検索は74～88%、合成スクリーンショット・キャンバス条件は0～8%でした。成功だけでなく失敗条件を分析した研究です。公開資料はスクリプト、測定CSV、論文、ポスターを含み、原画像全体と署名鍵は含みません。

## 資料の読み方

研究の問いと手法から読み、測定結果と失敗例を確認してください。再現ガイドで公開成果物と別途必要なローカルデータを区別できます。

[開発事例を見る](https://ysl-ryudo.github.io/ja/research/wisa/), [Portfolio](https://ysl-ryudo.github.io/ja/)

**A Verification Method for Game Image Assets Using C2PA Manifest Validation and Perceptual Hash-Based Similarity Analysis**の研究コードと記録済み実験結果です。

**WISA 2026・韓国済州でのポスター発表。** Young-Sang Leeは筆頭著者・発表者です。共著研究であり、MODパッケージprovenance研究およびGCTLAB開発とは別です。

## 研究課題と手法

ゲーム画像の再保存・変形後にも、出所情報と原画像候補を確認できるかを調べます。

1. C2PA Manifestの有無、署名、内容ハッシュを検証します。
2. 64-bit aHash・dHash・pHash・wHashを基準画像と比較します。
3. Top-1・Top-3検索性能と失敗条件を記録します。類似度は補助的な証拠であり、所有権の証明ではありません。

保存されたv3スクリプトは対照群・変形画像全体のハッシュを評価するもので、C2PA結果で分岐する商用サービスではありません。テスト証明書の信頼警告と署名・データハッシュ失敗を区別します。

## 記録された実験

研究用画像50枚、変形17種類（850枚）、対照条件5種類（250枚）を使用しました。C2PA検証は**1,150ファイル**、ハッシュ評価は**1,100クエリ×4方式＝4,400行**です。

| 条件 | 記録されたTop-1結果 |
|---|---:|
| JPEG Q95・50%縮小・メタデータ除去・透かし | 4方式とも100% |
| 20%クロップ | 74～88% |
| スクリーンショット模擬キャンバス | 0～8% |
| 5°回転のpHash | 82% |
| 15°・30°回転 | すべて12%以下 |

署名原本とバイトコピーは有効なclaimを保持し、その他の対照群・変形画像では検出されませんでした。スクリーンショット条件は縮小画像を配置した1920×1080合成キャンバスであり、あらゆる画面キャプチャーアプリを測定したものではありません。結果はこの50画像コーパスに限定されます。

![Top-1 accuracy across transformations](figures/hash_top1_all_methods.png)

## 再現と確認

コードと測定CSVを含みます。原本・署名画像コーパスと秘密署名鍵は**含めていない**ため、本リポジトリだけでは実験全体を再実行できません。対応する署名画像を`experiment/data/signed/<asset_type>/`に配置してください。元の署名段階は`scripts/01_embed_c2pa.py`に保存しており、ルートの`metadata/assets.csv`、`data/original/`、設定済みc2patool署名環境が必要です。

分離環境で`requirements.txt`をインストールし、c2patoolを用意してください。ローカル保存版にはv0.26.50があります。

```sh
python scripts/wisa_originality_v3_all.py --root ./experiment --c2patool c2patool
```

新しい実験ディレクトリーで実行すると、変形画像・結果がそこに書き込まれます。記録済みの`results/`は維持してください。復元したrequirementsにはPythonパッケージの厳密な版固定がありません。

公開準備ではZIP整合性、Python構文、結果行数、論文の主要数値との一致を確認しましたが、画像実験は再実行していません。CSVコピーのPC固有パスを相対化し、v3コードはdocstringの例示パスだけを変更して実行ロジックを維持しています。

## 論文・ポスター・著者

[論文](paper/WISA_2026_paper.pdf), [ポスター](paper/WISA_2026_poster.pdf), [記録済み結果](results/), [資料ハッシュ](ARTIFACTS.sha256)

Young-Sang Lee, Jung-Min Park, Won-Yong Lee, Geon Park, Myeong-Jae Lee, Yun-Ho Kim, Jung-Guen Lee, Dang Dai Tho, Hye-Young Kim。全所属・研究費謝辞・参考文献は論文に保持されています。論文・画像・外部ツール全体に一括ライセンスを付与するものではありません。
