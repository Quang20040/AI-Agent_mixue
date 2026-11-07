"""Initialize local configuration without overwriting secrets or private data."""
from pathlib import Path
import re
import secrets
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.tieng_viet import tao_mau  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main():
    env = ROOT / '.env'
    if not env.exists():
        password = secrets.token_hex(24)
        values = {
            'POSTGRES_PASSWORD': password,
            'JWT_SECRET_KEY': secrets.token_hex(32),
            'DATABASE_URL': f'postgresql+psycopg://beverageops:{password}@127.0.0.1:5432/beverageops',
        }
        content = (ROOT / '.env.example').read_text(encoding='utf-8')
        for key, value in values.items():
            content = re.sub(rf'^{key}=.*$', f'{key}={value}', content, flags=re.M)
        with env.open('x', encoding='utf-8') as handle:
            handle.write(content)
        print('Đã tạo cấu hình .env và khóa bảo mật riêng (không hiển thị khóa).')
    else:
        print('Đã giữ nguyên cấu hình .env hiện có.')
    for name in ['raw_private/sales_reports', 'raw_private/inventory_docs',
                 'raw_private/preparation_waste_logs', 'staging_private',
                 'processed_private', 'quality_reports', 'snapshots_private']:
        (ROOT / 'data' / name).mkdir(parents=True, exist_ok=True)
    # Extract the exact CSV contracts/examples supplied by document 04.
    doc = (ROOT / 'docs' / 'HUONG_DAN_CHUAN_BI_DU_LIEU.md').read_text(encoding='utf-8')
    sections = re.findall(r'### 3\.\d+\. `([^`]+\.csv)`(.*?)(?=\n### |\n## |\Z)', doc, re.S)
    for name, section in sections:
        example = re.search(r'```csv\n(.*?)```', section, re.S).group(1).strip() + '\n'
        for folder, content in [('templates', example.splitlines()[0] + '\n'),
                                ('public_examples', example)]:
            dest = ROOT / 'data' / folder / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                dest.write_text(content, encoding='utf-8-sig')
        dest = ROOT / 'data/staging_private' / name
        if not dest.exists():
            dest.write_text(example.splitlines()[0] + '\n', encoding='utf-8-sig')
    tao_mau(ROOT)
    print('Đã chuẩn bị 7 mẫu tiếng Việt trong DU_LIEU_CAN_NHAP; ví dụ nằm ở MAU_MINH_HOA.')


if __name__ == '__main__':
    main()
