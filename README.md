# Game Image Asset Verification, WISA 2026

[English](README.md), [Korean](README.ko.md), [Japanese](README.ja.md)

**WISA 2026: First author, poster presenter**

[27th World Conference on Information Security Applications](https://wisa.or.kr/)

26 ~ 28 Aug 2026, MAISON GLAD, Jeju, Korea

## Method and findings at a glance

The recorded experiment uses 50 game images, 17 transformations and 5 controls: 1,150 C2PA checks and 4,400 hash-evaluation rows. Cropping 20% yields 74 ~ 88% Top-1 retrieval; the synthetic screenshot-canvas condition yields 0 ~ 8%. These failure conditions matter as much as successful matching. The public archive includes scripts, measured CSVs, paper and poster; the original image corpus and signing keys are not bundled.

## Reading guide

Start with the research question and method, then inspect measured results and failure cases. Use the reproduction guide to distinguish the public artifacts from required local data.

[Explore the case](https://ysl-ryudo.github.io/en/research/wisa/), [Portfolio](https://ysl-ryudo.github.io/en/)

Research code and recorded results for **A Verification Method for Game Image Assets Using C2PA Manifest Validation and Perceptual Hash-Based Similarity Analysis**.

**WISA 2026, Poster presentation, Jeju, Republic of Korea.** Young-Sang Lee is the first author and poster presenter. This is a coauthored study; it is independent of the MOD-package provenance project and GCTLAB development.

## Research question and method

Can provenance and original candidates still be verified after game images are re-saved or transformed?

1. Validate C2PA manifest presence, signature and content hash.
2. Compare 64-bit aHash, dHash, pHash and wHash against the reference images.
3. Report Top-1/Top-3 retrieval and failure conditions. Similarity is supporting evidence, not proof of ownership.

The archived v3 script evaluates hashes across control/transformed queries; it does not implement a deployed C2PA-gated production service. A test-certificate trust warning is distinguished from signature/data-hash failure.

## Recorded experiment

50 researcher-created game assets, 17 transformations (850 images), and 5 controls (250 images). C2PA validation covers **1,150 files**. Hash evaluation covers **1,100 queries × 4 methods = 4,400 rows**.

| Condition | Recorded Top-1 result |
|---|---:|
| JPEG Q95, 50% resize, metadata removal, watermark | 100% for all four hashes |
| 20% crop | 74 ~ 88% |
| Screenshot-style canvas | 0 ~ 8% |
| 5° rotation, pHash | 82% |
| 15°/30° rotation | No method exceeds 12% |

Signed originals and byte copies retained valid claims; other controls and transformed images had no detectable claim. The screenshot condition is a synthetic 1920×1080 canvas containing a resized image, not a measurement of every screenshot application. These results are specific to this 50-image corpus.

![Top-1 accuracy across transformations](figures/hash_top1_all_methods.png)

## Reproduce and inspect

The source and measured CSVs are included. The original/signed image corpus and private signing keys are **not bundled**; the full experiment cannot be rerun from this repository alone. Put the matching signed corpus under `experiment/data/signed/<asset_type>/`. The original signing stage is preserved in `scripts/01_embed_c2pa.py`; it expects root-level `metadata/assets.csv` and `data/original/` plus a correctly configured c2patool signing environment.

Use an isolated environment, install `requirements.txt`, and provide c2patool (the local archive contains v0.26.50). Run:

```sh
python scripts/wisa_originality_v3_all.py --root ./experiment --c2patool c2patool
```

Run in a new experiment directory: the script writes transformed images and results there. Keep the recorded `results/` unchanged. Exact Python package versions were not captured in the recovered requirements file.

The packaging check verified ZIP integrity, Python syntax, result row counts and agreement with the paper's reported conditions; it did not rerun the image experiment. Machine-specific paths were made relative in CSV copies. Only the v3 docstring's example path was changed; executable algorithm logic is preserved.

## Paper, poster and authors

[Paper](paper/WISA_2026_paper.pdf), [Poster](paper/WISA_2026_poster.pdf), [Recorded results](results/), [Artifact hashes](ARTIFACTS.sha256)

Young-Sang Lee, Jung-Min Park, Won-Yong Lee, Geon Park, Myeong-Jae Lee, Yun-Ho Kim, Jung-Guen Lee, Dang Dai Tho, and Hye-Young Kim. Full affiliations, funding acknowledgement and references are preserved in the paper. No blanket license is asserted over the paper, images or third-party tools.
