# -*- coding: utf-8 -*-
r"""
WISA Originality Verification v3
게임 이미지 리소스 원본성 판별 실험 파이프라인 - Rotation 포함 버전

v3 변경점:
1) data/signed 기준으로 data/transformed_v3 자동 생성
2) 기존 14종 변형 + rotation 3종(rotate_5, rotate_15, rotate_30) 추가
3) results_v3에 C2PA/Hash 결과, 그래프, C2PA 로그 요약 txt/csv 생성

실행 예:
python wisa_originality_v3_all.py --root "./experiment" --c2patool c2patool
"""

from pathlib import Path
import argparse
import shutil
import subprocess
import re
import sys
from collections import Counter, defaultdict

import pandas as pd
from PIL import Image, ImageEnhance, ImageDraw, ImageOps
import imagehash
import matplotlib.pyplot as plt

IMG_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff'}

TRANSFORM_ORDER = [
    'jpeg_q95', 'jpeg_q75', 'jpeg_q50',
    'resize_50', 'resize_25',
    'crop_10', 'crop_20',
    'brightness_120', 'saturation_120',
    'png_to_jpeg', 'png_to_webp',
    'metadata_strip', 'watermark', 'screenshot',
    'rotate_5', 'rotate_15', 'rotate_30',
]

CONTROL_ORDER = ['byte_copy', 'pillow_resave_png', 'metadata_strip_png', 'jpeg_q95', 'webp_q90']


def iter_images(root: Path):
    if not root.exists():
        return
    for p in root.rglob('*'):
        if p.is_file() and p.suffix.lower() in IMG_EXTS:
            yield p


def safe_id(s: str) -> str:
    return re.sub(r'[^A-Za-z0-9가-힣_.-]+', '_', str(s)).strip('_')


def normalize_stem(stem: str) -> str:
    return stem.lower().replace('-', '_').replace(' ', '_')


def infer_true_asset(query_path: Path, reference_stems):
    q = normalize_stem(query_path.stem)
    candidates = []
    for ref in reference_stems:
        r = normalize_stem(ref)
        if q == r or q.startswith(r + '_') or q.startswith(r + '-') or q.startswith(r):
            candidates.append(ref)
    if not candidates:
        return None
    return sorted(candidates, key=len, reverse=True)[0]


def infer_transform(query_path: Path, true_asset, group: str):
    if not true_asset:
        return group
    stem = normalize_stem(query_path.stem)
    ref = normalize_stem(true_asset)
    t = stem[len(ref):].strip('_- ')
    return t if t else group


def open_rgb(path: Path):
    img = Image.open(path)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    return img


def center_crop_by_percent(img: Image.Image, percent: float):
    """percent=0.20이면 가로/세로 전체 폭의 20%를 제거한 중앙 영역을 crop한다."""
    w, h = img.size
    new_w = max(1, int(w * (1.0 - percent)))
    new_h = max(1, int(h * (1.0 - percent)))
    left = (w - new_w) // 2
    top = (h - new_h) // 2
    return img.crop((left, top, left + new_w, top + new_h))


def save_jpeg(img: Image.Image, path: Path, quality: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert('RGB').save(path, format='JPEG', quality=quality)


def save_png(img: Image.Image, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert('RGB').save(path, format='PNG')


def save_webp(img: Image.Image, path: Path, quality: int = 90):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert('RGB').save(path, format='WEBP', quality=quality)


def make_screenshot_canvas(img: Image.Image):
    canvas_w, canvas_h = 1920, 1080
    canvas = Image.new('RGB', (canvas_w, canvas_h), (20, 20, 24))
    # 원본이 화면 일부로 들어가는 상황을 가정: 긴 변 기준 70% 이하로 축소
    max_w, max_h = int(canvas_w * 0.70), int(canvas_h * 0.70)
    tmp = img.copy().convert('RGB')
    tmp.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    x = (canvas_w - tmp.width) // 2
    y = (canvas_h - tmp.height) // 2
    canvas.paste(tmp, (x, y))
    return canvas


def add_watermark(img: Image.Image):
    out = img.copy().convert('RGB')
    draw = ImageDraw.Draw(out)
    w, h = out.size
    text = 'WISA TEST'
    # 오른쪽 아래 반투명 효과 대신 밝은 외곽 텍스트를 직접 그림
    pos = (max(5, w - int(w * 0.35)), max(5, h - int(h * 0.12)))
    draw.text((pos[0]+2, pos[1]+2), text, fill=(255, 255, 255))
    draw.text(pos, text, fill=(220, 40, 40))
    return out


def apply_transform(src: Path, transform: str, dst: Path):
    img = open_rgb(src)
    w, h = img.size

    if transform == 'jpeg_q95':
        save_jpeg(img, dst.with_suffix('.jpg'), 95); return dst.with_suffix('.jpg')
    if transform == 'jpeg_q75':
        save_jpeg(img, dst.with_suffix('.jpg'), 75); return dst.with_suffix('.jpg')
    if transform == 'jpeg_q50':
        save_jpeg(img, dst.with_suffix('.jpg'), 50); return dst.with_suffix('.jpg')
    if transform == 'resize_50':
        out = img.resize((max(1, w//2), max(1, h//2)), Image.Resampling.LANCZOS)
        save_png(out, dst.with_suffix('.png')); return dst.with_suffix('.png')
    if transform == 'resize_25':
        out = img.resize((max(1, w//4), max(1, h//4)), Image.Resampling.LANCZOS)
        save_png(out, dst.with_suffix('.png')); return dst.with_suffix('.png')
    if transform == 'crop_10':
        out = center_crop_by_percent(img, 0.10)
        save_png(out, dst.with_suffix('.png')); return dst.with_suffix('.png')
    if transform == 'crop_20':
        out = center_crop_by_percent(img, 0.20)
        save_png(out, dst.with_suffix('.png')); return dst.with_suffix('.png')
    if transform == 'brightness_120':
        out = ImageEnhance.Brightness(img).enhance(1.20)
        save_png(out, dst.with_suffix('.png')); return dst.with_suffix('.png')
    if transform == 'saturation_120':
        out = ImageEnhance.Color(img).enhance(1.20)
        save_png(out, dst.with_suffix('.png')); return dst.with_suffix('.png')
    if transform == 'png_to_jpeg':
        save_jpeg(img, dst.with_suffix('.jpg'), 95); return dst.with_suffix('.jpg')
    if transform == 'png_to_webp':
        save_webp(img, dst.with_suffix('.webp'), 90); return dst.with_suffix('.webp')
    if transform == 'metadata_strip':
        # 픽셀만 새 이미지에 복사하여 메타데이터 제거
        clean = Image.new('RGB', img.size)
        clean.putdata(list(img.getdata()))
        save_png(clean, dst.with_suffix('.png')); return dst.with_suffix('.png')
    if transform == 'watermark':
        out = add_watermark(img)
        save_png(out, dst.with_suffix('.png')); return dst.with_suffix('.png')
    if transform == 'screenshot':
        out = make_screenshot_canvas(img)
        save_png(out, dst.with_suffix('.png')); return dst.with_suffix('.png')
    if transform.startswith('rotate_'):
        angle = int(transform.split('_')[1])
        # 일반적인 회전 저장을 가정: 확장 캔버스 + 흰 배경
        out = img.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC, fillcolor=(255, 255, 255))
        save_png(out, dst.with_suffix('.png')); return dst.with_suffix('.png')

    raise ValueError(f'Unknown transform: {transform}')


def create_transforms_v3(signed_dir: Path, transformed_dir: Path, overwrite=False):
    rows = []
    transformed_dir.mkdir(parents=True, exist_ok=True)
    for src in iter_images(signed_dir):
        asset_type = src.parent.name.lower()
        stem = src.stem
        for transform in TRANSFORM_ORDER:
            base = transformed_dir / asset_type / f'{stem}_{transform}'
            # 실제 확장자는 transform별로 달라질 수 있음
            possible = list((transformed_dir / asset_type).glob(f'{stem}_{transform}.*')) if (transformed_dir / asset_type).exists() else []
            if possible and not overwrite:
                out_path = possible[0]
            else:
                out_path = apply_transform(src, transform, base)
            rows.append({'src': str(src), 'asset_type': asset_type, 'asset_id': stem, 'transform': transform, 'dst': str(out_path)})
    return pd.DataFrame(rows)


def create_controls_v3(signed_dir: Path, controls_dir: Path, overwrite=False):
    rows = []
    controls_dir.mkdir(parents=True, exist_ok=True)
    for src in iter_images(signed_dir):
        asset_type = src.parent.name.lower()
        stem = src.stem

        def out(group, suffix):
            return controls_dir / asset_type / group / f"{stem}_{group}{suffix}"

        dst = out('byte_copy', src.suffix.lower())
        if overwrite or not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        rows.append({'control': 'byte_copy', 'src': str(src), 'dst': str(dst)})

        dst = out('pillow_resave_png', '.png')
        if overwrite or not dst.exists():
            save_png(open_rgb(src), dst)
        rows.append({'control': 'pillow_resave_png', 'src': str(src), 'dst': str(dst)})

        dst = out('metadata_strip_png', '.png')
        if overwrite or not dst.exists():
            img = open_rgb(src)
            clean = Image.new('RGB', img.size)
            clean.putdata(list(img.getdata()))
            save_png(clean, dst)
        rows.append({'control': 'metadata_strip_png', 'src': str(src), 'dst': str(dst)})

        dst = out('jpeg_q95', '.jpg')
        if overwrite or not dst.exists():
            save_jpeg(open_rgb(src), dst, 95)
        rows.append({'control': 'jpeg_q95', 'src': str(src), 'dst': str(dst)})

        dst = out('webp_q90', '.webp')
        if overwrite or not dst.exists():
            save_webp(open_rgb(src), dst, 90)
        rows.append({'control': 'webp_q90', 'src': str(src), 'dst': str(dst)})

    return pd.DataFrame(rows)


NO_MANIFEST_PATTERNS = [
    r'no\s+claim\s+found', r'no\s+manifest', r'no\s+c2pa', r'not\s+c2pa',
    r'could\s+not\s+find\s+(a\s+)?manifest', r'manifest\s+not\s+found',
    r'claim\s+not\s+found'
]
MANIFEST_HINTS = [r'\bmanifest\b', r'\bclaim\b', r'\bassertion\b', r'\bsignature\b', r'c2pa', r'content\s+credentials']
TRUST_WARNING_PATTERNS = [r'trust\s+warning', r'untrusted', r'certificate', r'cert\s', r'could\s+not\s+verify\s+trust']
VALID_STATE_PATTERN = r'"validation_state"\s*:\s*"Valid"'
SIGNATURE_VALID_PATTERNS = [r'claimSignature\.validated', r'claim signature valid']
DATA_HASH_VALID_PATTERNS = [r'assertion\.dataHash\.match', r'data hash valid']


def has_any(patterns, text):
    return any(re.search(p, text, flags=re.I | re.S) for p in patterns)


def classify_c2pa(stdout, stderr, returncode):
    text = f"{stdout}\n{stderr}"
    text_l = text.lower()
    no_claim = has_any(NO_MANIFEST_PATTERNS, text_l)
    manifest_hint = has_any(MANIFEST_HINTS, text_l)
    validation_state_valid = bool(re.search(VALID_STATE_PATTERN, text, flags=re.I))
    signature_valid = has_any(SIGNATURE_VALID_PATTERNS, text)
    data_hash_valid = has_any(DATA_HASH_VALID_PATTERNS, text)
    trust_warning = has_any(TRUST_WARNING_PATTERNS, text_l)

    if no_claim:
        status = 'NO_CLAIM_FOUND'
        manifest_present = 0
        validation_success = 0
        c2pa_status = 'S2'
        error_type = 'no_claim_found'
    elif validation_state_valid or (manifest_hint and signature_valid and data_hash_valid):
        status = 'VALID_WITH_TRUST_WARNING' if trust_warning else 'VALID'
        manifest_present = 1
        validation_success = 1
        c2pa_status = 'S0'
        error_type = 'trust_warning' if trust_warning else ''
    elif returncode != 0:
        status = 'TOOL_ERROR_OR_UNKNOWN'
        manifest_present = int(manifest_hint)
        validation_success = 0
        c2pa_status = 'S3'
        error_type = 'tool_error_or_unknown'
    elif manifest_hint:
        status = 'MANIFEST_PRESENT_BUT_NOT_VALID'
        manifest_present = 1
        validation_success = 0
        c2pa_status = 'S1'
        error_type = 'manifest_present_validation_unknown'
    else:
        status = 'UNKNOWN_NO_MANIFEST'
        manifest_present = 0
        validation_success = 0
        c2pa_status = 'S2'
        error_type = 'unknown_no_manifest'

    return dict(
        status=status,
        manifest_present=manifest_present,
        validation_success=validation_success,
        c2pa_status=c2pa_status,
        error_type=error_type,
        validation_state_valid=int(validation_state_valid),
        signature_valid=int(signature_valid),
        data_hash_valid=int(data_hash_valid),
        trust_warning_detected=int(trust_warning),
        no_claim_found=int(no_claim),
    )


def run_c2patool(c2patool, image_path: Path, timeout=60):
    cmd = [str(c2patool), str(image_path)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding='utf-8', errors='replace')
        return p.returncode, p.stdout or '', p.stderr or '', ' '.join(cmd)
    except FileNotFoundError as e:
        return 127, '', str(e), ' '.join(cmd)
    except subprocess.TimeoutExpired as e:
        return 124, e.stdout or '', e.stderr or 'timeout', ' '.join(cmd)


def find_c2patool(user_value):
    if user_value:
        return user_value
    found = shutil.which('c2patool')
    if found:
        return found
    default = Path(r'C:\c2patool\c2patool.exe')
    if default.exists():
        return str(default)
    return 'c2patool'


def collect_c2pa_targets(root: Path):
    groups = [
        ('signed_original', root / 'data' / 'signed'),
        ('control', root / 'data' / 'controls_v3'),
        ('transformed', root / 'data' / 'transformed_v3'),
        ('platform', root / 'data' / 'platform_downloaded')
    ]
    for group, d in groups:
        if d.exists():
            for p in iter_images(d):
                yield group, p


def validate_all(root: Path, c2patool, out_dir: Path):
    logs_dir = out_dir / 'c2pa_logs'
    logs_dir.mkdir(parents=True, exist_ok=True)
    signed_dir = root / 'data' / 'signed'
    ref_stems = [p.stem for p in iter_images(signed_dir)] if signed_dir.exists() else []
    rows = []

    for group, p in collect_c2pa_targets(root):
        true_asset = infer_true_asset(p, ref_stems)
        transform = 'signed_original' if group == 'signed_original' else infer_transform(p, true_asset, group)
        asset_type = p.parent.name.lower()

        try:
            if group == 'control':
                rel = p.relative_to(root / 'data' / 'controls_v3')
                asset_type = rel.parts[0].lower()
                transform = rel.parts[1].lower()
            elif group == 'transformed':
                rel = p.relative_to(root / 'data' / 'transformed_v3')
                asset_type = rel.parts[0].lower()
            elif group == 'platform':
                rel = p.relative_to(root / 'data' / 'platform_downloaded')
                transform = rel.parts[0].lower()
        except Exception:
            pass

        variant_id = safe_id(p.stem)
        code, stdout, stderr, command = run_c2patool(c2patool, p)
        cls = classify_c2pa(stdout, stderr, code)

        log_name = safe_id(f"{group}_{asset_type}_{variant_id}") + '.txt'
        log_path = logs_dir / log_name
        log_path.write_text(f"COMMAND: {command}\n\nRETURN_CODE: {code}\n\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}\n",
                            encoding='utf-8', errors='replace')

        rows.append({
            'group': group, 'variant_id': variant_id, 'true_asset': true_asset or '',
            'asset_type': asset_type, 'transform': transform, 'file_path': str(p),
            'exit_code': code, 'log_file': str(log_path), **cls
        })

    df = pd.DataFrame(rows)
    df.to_csv(out_dir / 'c2pa_results_v3.csv', index=False, encoding='utf-8-sig')
    if not df.empty:
        df.groupby(['group', 'c2pa_status', 'status'], dropna=False).size().reset_index(name='count') \
          .to_csv(out_dir / 'c2pa_summary_by_group.csv', index=False, encoding='utf-8-sig')

        summary = df.groupby(['group', 'transform']).agg(
            n=('variant_id','count'),
            manifest_presence_rate=('manifest_present','mean'),
            validation_success_rate=('validation_success','mean'),
            trust_warning_rate=('trust_warning_detected','mean'),
            no_claim_rate=('no_claim_found','mean')
        ).reset_index()
        for col in ['manifest_presence_rate', 'validation_success_rate', 'trust_warning_rate', 'no_claim_rate']:
            summary[col] *= 100
        summary.to_csv(out_dir / 'c2pa_summary_by_transform.csv', index=False, encoding='utf-8-sig')
    return df


HASH_METHODS = {
    'ahash': imagehash.average_hash,
    'dhash': imagehash.dhash,
    'phash': imagehash.phash,
    'whash': imagehash.whash,
}


def compute_hashes(path: Path):
    img = open_rgb(path)
    return {name: func(img) for name, func in HASH_METHODS.items()}


def build_reference_db(signed_dir: Path):
    refs = []
    for p in iter_images(signed_dir):
        refs.append({'asset_id': p.stem, 'asset_type': p.parent.name.lower(), 'file_path': str(p), 'hashes': compute_hashes(p)})
    return refs


def collect_hash_queries(root: Path):
    for group, d in [('control', root/'data'/'controls_v3'), ('transformed', root/'data'/'transformed_v3'), ('platform', root/'data'/'platform_downloaded')]:
        if d.exists():
            for p in iter_images(d):
                yield group, p


def evaluate_hashes(root: Path, out_dir: Path):
    signed_dir = root / 'data' / 'signed'
    refs = build_reference_db(signed_dir)
    ref_stems = [r['asset_id'] for r in refs]
    rows = []
    if not refs:
        df = pd.DataFrame()
        df.to_csv(out_dir / 'hash_results_v3.csv', index=False, encoding='utf-8-sig')
        return df

    for group, qpath in collect_hash_queries(root):
        true_asset = infer_true_asset(qpath, ref_stems)
        if not true_asset:
            continue

        transform = infer_transform(qpath, true_asset, group)
        asset_type = ''
        try:
            if group == 'control':
                rel = qpath.relative_to(root / 'data' / 'controls_v3')
                asset_type = rel.parts[0].lower()
                transform = rel.parts[1].lower()
            elif group == 'transformed':
                rel = qpath.relative_to(root / 'data' / 'transformed_v3')
                asset_type = rel.parts[0].lower()
            elif group == 'platform':
                rel = qpath.relative_to(root / 'data' / 'platform_downloaded')
                transform = rel.parts[0].lower()
        except Exception:
            pass
        if not asset_type:
            match = next((r for r in refs if r['asset_id'] == true_asset), None)
            asset_type = match['asset_type'] if match else ''

        try:
            qhashes = compute_hashes(qpath)
        except Exception as e:
            rows.append({'group': group, 'variant_id': safe_id(qpath.stem), 'true_asset': true_asset,
                         'asset_type': asset_type, 'transform': transform, 'hash_method': 'ERROR', 'error': str(e)})
            continue

        for method, qh in qhashes.items():
            dists = [(ref['asset_id'], int(qh - ref['hashes'][method])) for ref in refs]
            dists_sorted = sorted(dists, key=lambda x: x[1])
            top1_asset, top1_distance = dists_sorted[0]
            top2_asset, top2_distance = dists_sorted[1] if len(dists_sorted) > 1 else ('', None)
            top3_assets = [a for a, _ in dists_sorted[:3]]
            margin = '' if top2_distance is None else int(top2_distance - top1_distance)
            rows.append({
                'group': group, 'variant_id': safe_id(qpath.stem), 'true_asset': true_asset,
                'asset_type': asset_type, 'transform': transform, 'hash_method': method,
                'top1_asset': top1_asset, 'top1_distance': int(top1_distance),
                'top2_asset': top2_asset, 'top2_distance': '' if top2_distance is None else int(top2_distance),
                'top3_assets': '|'.join(top3_assets), 'margin': margin,
                'top1_correct': int(top1_asset == true_asset),
                'top3_correct': int(true_asset in top3_assets),
                'query_file': str(qpath)
            })

    df = pd.DataFrame(rows)
    df.to_csv(out_dir / 'hash_results_v3.csv', index=False, encoding='utf-8-sig')
    if not df.empty and 'top1_correct' in df.columns:
        work = df[df['hash_method'] != 'ERROR'].copy()
        work['margin_num'] = pd.to_numeric(work['margin'], errors='coerce')
        summary_tm = work.groupby(['group','transform','hash_method']).agg(
            n=('variant_id','count'),
            top1_accuracy=('top1_correct','mean'),
            top3_accuracy=('top3_correct','mean'),
            avg_top1_distance=('top1_distance','mean'),
            avg_margin=('margin_num','mean')
        ).reset_index()
        summary_tm['top1_accuracy'] *= 100
        summary_tm['top3_accuracy'] *= 100
        summary_tm.to_csv(out_dir / 'hash_summary_by_transform_method.csv', index=False, encoding='utf-8-sig')

        summary_at = work.groupby(['asset_type','hash_method']).agg(
            n=('variant_id','count'),
            top1_accuracy=('top1_correct','mean'),
            top3_accuracy=('top3_correct','mean'),
            avg_top1_distance=('top1_distance','mean'),
            avg_margin=('margin_num','mean')
        ).reset_index()
        summary_at['top1_accuracy'] *= 100
        summary_at['top3_accuracy'] *= 100
        summary_at.to_csv(out_dir / 'hash_summary_by_asset_type_method.csv', index=False, encoding='utf-8-sig')

        work[work['top1_correct'] == 0].sort_values(['transform','hash_method','top1_distance']) \
            .to_csv(out_dir / 'hash_failures_top1.csv', index=False, encoding='utf-8-sig')
    return df


def ordered_transforms(values):
    order = CONTROL_ORDER + TRANSFORM_ORDER + ['signed_original']
    seen = list(values)
    return sorted(seen, key=lambda x: order.index(x) if x in order else len(order) + seen.index(x))


def plot_results(out_dir: Path):
    fig_dir = out_dir / 'figures'
    fig_dir.mkdir(parents=True, exist_ok=True)

    c2pa_summary = out_dir / 'c2pa_summary_by_transform.csv'
    if c2pa_summary.exists():
        df = pd.read_csv(c2pa_summary)
        if not df.empty:
            agg = df.groupby('transform').agg(
                manifest_presence_rate=('manifest_presence_rate','mean'),
                validation_success_rate=('validation_success_rate','mean')
            ).reset_index()
            order = ordered_transforms(agg['transform'].tolist())
            agg['transform'] = pd.Categorical(agg['transform'], categories=order, ordered=True)
            agg = agg.sort_values('transform')
            plt.figure(figsize=(16, 5))
            x = range(len(agg))
            width = 0.35
            plt.bar([i - width/2 for i in x], agg['manifest_presence_rate'], width, label='Manifest presence')
            plt.bar([i + width/2 for i in x], agg['validation_success_rate'], width, label='Validation success')
            plt.xticks(list(x), agg['transform'].astype(str), rotation=45, ha='right')
            plt.ylabel('Rate (%)')
            plt.title('C2PA Manifest Preservation and Validation by Transform')
            plt.legend()
            plt.tight_layout()
            plt.savefig(fig_dir / 'c2pa_by_transform.png', dpi=200)
            plt.close()

    hash_summary = out_dir / 'hash_summary_by_transform_method.csv'
    if hash_summary.exists():
        df = pd.read_csv(hash_summary)
        if not df.empty:
            pivot = df.pivot_table(index='transform', columns='hash_method', values='top1_accuracy', aggfunc='mean')
            if not pivot.empty:
                order = ordered_transforms(pivot.index.tolist())
                pivot = pivot.reindex([x for x in order if x in pivot.index])
                plt.figure(figsize=(16, 5))
                for col in pivot.columns:
                    plt.plot(pivot.index, pivot[col], marker='o', label=col)
                plt.xticks(rotation=45, ha='right')
                plt.ylabel('Top-1 Accuracy (%)')
                plt.title('Top-1 Accuracy by Hash Method')
                plt.legend()
                plt.tight_layout()
                plt.savefig(fig_dir / 'hash_top1_all_methods.png', dpi=200)
                plt.close()


def make_log_bundle(out_dir: Path):
    logs_dir = out_dir / 'c2pa_logs'
    if not logs_dir.exists():
        return
    rows_path = out_dir / 'c2pa_results_v3.csv'
    if not rows_path.exists():
        return
    df = pd.read_csv(rows_path)
    lines = []
    lines.append('='*90)
    lines.append('C2PA LOG MERGED SUMMARY v3')
    lines.append('='*90)
    lines.append(f'Total log files: {len(df)}')
    lines.append('')
    lines.append('[1] Overall status counts')
    for status, count in df['status'].value_counts().items():
        lines.append(f'- {status}: {count} ({count/len(df)*100:.1f}%)')
    lines.append('')
    lines.append('[2] Summary by group')
    g = df.groupby('group').agg(
        n=('variant_id','count'),
        manifest_pct=('manifest_present','mean'),
        valid_pct=('validation_success','mean'),
        no_claim_pct=('no_claim_found','mean'),
        trust_warning_pct=('trust_warning_detected','mean')
    ).reset_index()
    for c in ['manifest_pct','valid_pct','no_claim_pct','trust_warning_pct']:
        g[c] *= 100
    lines.append(g.to_string(index=False, formatters={c:'{:.1f}'.format for c in ['manifest_pct','valid_pct','no_claim_pct','trust_warning_pct']}))
    lines.append('')
    lines.append('[3] Summary by transform')
    t = df.groupby('transform').agg(
        n=('variant_id','count'),
        manifest_pct=('manifest_present','mean'),
        valid_pct=('validation_success','mean'),
        no_claim_pct=('no_claim_found','mean')
    ).reset_index()
    for c in ['manifest_pct','valid_pct','no_claim_pct']:
        t[c] *= 100
    order = ordered_transforms(t['transform'].tolist())
    t['transform'] = pd.Categorical(t['transform'], categories=order, ordered=True)
    t = t.sort_values('transform')
    lines.append(t.to_string(index=False, formatters={c:'{:.1f}'.format for c in ['manifest_pct','valid_pct','no_claim_pct']}))
    lines.append('')
    lines.append('[4] Representative valid examples')
    valid = df[df['manifest_present'].eq(1)].head(8)
    for _, r in valid.iterrows():
        lines.append(f"- {Path(r['log_file']).name} | group={r['group']} | transform={r['transform']} | status={r['status']} | signature_valid={r['signature_valid']} | data_hash_valid={r['data_hash_valid']} | trust_warning={r['trust_warning_detected']}")
    lines.append('')
    lines.append('[5] Representative No-claim examples')
    nc = df[df['no_claim_found'].eq(1)].head(12)
    for _, r in nc.iterrows():
        lines.append(f"- {Path(r['log_file']).name} | group={r['group']} | transform={r['transform']} | return_code={r['exit_code']} | Error: No claim found")
    lines.append('')
    lines.append('[6] Korean interpretation draft')
    lines.append('본 로그 요약 결과, C2PA Manifest는 signed original 및 byte-level copy 조건에서는 유지되고 validation_state가 Valid로 확인된다. 반면 Pillow 재저장, JPEG/WebP 변환, metadata strip 및 회전/크롭/리사이즈/스크린샷 등 재인코딩 기반 변형 조건에서는 c2patool이 No claim found를 반환한다. 이는 해당 처리 과정에서 C2PA claim 또는 Manifest가 파일에서 제거되었음을 의미한다. 따라서 C2PA는 원본성 검증의 1차 근거로 유효하지만, 일반적인 이미지 저장 및 변형 파이프라인에서는 손실될 수 있으며, 이 경우 지각 해시 기반 유사도 비교가 파생본 판별의 보조 근거로 필요하다.')
    (out_dir / 'c2pa_logs_merged_summary.txt').write_text('\n'.join(lines), encoding='utf-8')
    df[['group','asset_type','transform','variant_id','exit_code','status','manifest_present','validation_success','signature_valid','data_hash_valid','trust_warning_detected','no_claim_found','log_file']] \
        .to_csv(out_dir / 'c2pa_log_summary.csv', index=False, encoding='utf-8-sig')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, help='WISA 프로젝트 루트 폴더')
    parser.add_argument('--c2patool', default=None, help='c2patool.exe 경로')
    parser.add_argument('--out', default='results_v3', help='결과 폴더명')
    parser.add_argument('--overwrite', action='store_true', help='transformed_v3, controls_v3 파일을 다시 생성')
    parser.add_argument('--skip-generate', action='store_true')
    parser.add_argument('--skip-c2pa', action='store_true')
    parser.add_argument('--skip-hash', action='store_true')
    parser.add_argument('--skip-plots', action='store_true')
    args = parser.parse_args()

    root = Path(args.root)
    out_dir = root / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    signed_dir = root / 'data' / 'signed'
    if not signed_dir.exists():
        print('[ERROR] data/signed 폴더가 없습니다:', signed_dir)
        sys.exit(1)

    if not args.skip_generate:
        print('[1/5] transformed_v3 생성: 기존 14종 + rotation 3종')
        trans_df = create_transforms_v3(signed_dir, root / 'data' / 'transformed_v3', args.overwrite)
        trans_df.to_csv(out_dir / 'transformed_files_v3.csv', index=False, encoding='utf-8-sig')
        print('  transformed files:', len(trans_df))
        print('[2/5] controls_v3 생성')
        controls_df = create_controls_v3(signed_dir, root / 'data' / 'controls_v3', args.overwrite)
        controls_df.to_csv(out_dir / 'control_group_files.csv', index=False, encoding='utf-8-sig')
        print('  control files:', len(controls_df))
    else:
        print('[1/5][2/5] 이미지 생성 생략')

    if not args.skip_c2pa:
        print('[3/5] C2PA 검증')
        c2pa = find_c2patool(args.c2patool)
        print('  c2patool:', c2pa)
        c2pa_df = validate_all(root, c2pa, out_dir)
        print('  c2pa rows:', len(c2pa_df))
        make_log_bundle(out_dir)
    else:
        print('[3/5] C2PA 검증 생략')

    if not args.skip_hash:
        print('[4/5] 해시 재식별 평가')
        hash_df = evaluate_hashes(root, out_dir)
        print('  hash rows:', len(hash_df))
    else:
        print('[4/5] 해시 평가 생략')

    if not args.skip_plots:
        print('[5/5] 그래프 생성')
        plot_results(out_dir)
    else:
        print('[5/5] 그래프 생성 생략')

    print('\nDONE')
    print('결과 폴더:', out_dir)
    print('- transformed_files_v3.csv')
    print('- c2pa_results_v3.csv')
    print('- c2pa_logs_merged_summary.txt')
    print('- c2pa_log_summary.csv')
    print('- hash_results_v3.csv')
    print('- hash_summary_by_transform_method.csv')
    print('- hash_failures_top1.csv')
    print('- figures/')


if __name__ == '__main__':
    main()
