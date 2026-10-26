"""MoneyPrinterTurbo 应用包元数据。"""

from app.utils import system_certs

__version__ = "1.3.9"

# 必须早于 edge-tts 等库的导入：它们在导入时就用 certifi 创建 SSL 上下文，
# 公司 TLS 代理（如 Zscaler）的根证书只在系统证书库中。
system_certs.install()
