#!/usr/bin/env python3
"""
安全检查脚本，用于检测代码中的潜在敏感信息
"""

import re
import sys


def check_secrets_in_file(file_path):
    """检查单个文件中的敏感信息"""
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # 检查OpenAI风格的API密钥 (sk- followed by 20+ alphanumeric chars)
        api_key_pattern = r"sk-[a-zA-Z0-9]{20,}"
        api_keys = re.findall(api_key_pattern, content)
        if api_keys:
            print(f"::error::Potential API key found in {file_path}: {api_keys[0]}...", file=sys.stderr)
            return False

        # 检查私钥
        private_key_pattern = r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----"
        private_keys = re.findall(private_key_pattern, content)
        if private_keys:
            print(f"::error::Private key found in {file_path}", file=sys.stderr)
            return False

        # 检查密码字段中的硬编码值
        password_pattern = r'(password|pwd|pass)\s*[=:]\s*["\'][^"\']{5,}["\']'
        passwords = re.findall(password_pattern, content, re.IGNORECASE)
        if passwords:
            print(f"::warning::Possible hardcoded password found in {file_path}", file=sys.stderr)

        return True
    except Exception as e:
        print(f"Error reading file {file_path}: {e}", file=sys.stderr)
        return False


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("Usage: check_secrets.py <file1> [file2] ...", file=sys.stderr)
        sys.exit(1)

    files = sys.argv[1:]
    all_clean = True

    for file_path in files:
        # 只检查Python文件和其他常见配置文件
        if any(file_path.endswith(ext) for ext in [".py", ".json", ".yaml", ".yml", ".toml", ".md"]):
            if not check_secrets_in_file(file_path):
                all_clean = False

    if not all_clean:
        sys.exit(1)


if __name__ == "__main__":
    main()
