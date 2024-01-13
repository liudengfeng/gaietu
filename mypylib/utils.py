from pathlib import Path

import toml


def get_secrets():
    """获取密码"""
    secrets = {}
    current_dir: Path = Path(__file__).parent.parent
    fp = current_dir / ".streamlit/secrets.toml"
    with open(fp, encoding="utf-8") as f:
        secrets_file_str = f.read()
        secrets.update(toml.loads(secrets_file_str))
    return secrets
