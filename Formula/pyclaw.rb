class Pyclaw < Formula
  include Language::Python::Virtualenv

  desc "Multi-channel AI gateway with extensible messaging integrations"
  homepage "https://github.com/chensaics/openclaw-py"
  url "https://github.com/chensaics/openclaw-py/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "PLACEHOLDER_SHA256"
  license "MIT"
  head "https://github.com/chensaics/openclaw-py.git", branch: "main"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  def caveats
    <<~EOS
      To get started, set at least one LLM provider key:

        export OPENAI_API_KEY="sk-..."

      Then start the gateway:

        pyclaw gateway --port 18789

      Or run the desktop UI:

        pyclaw ui

      See the full documentation at:
        https://github.com/chensaics/openclaw-py#readme
    EOS
  end

  test do
    assert_match "pyclaw", shell_output("#{bin}/pyclaw --help")
  end
end
