"""Entrypoint Lambda v3 (NÃO implantado — deploy pausado por custo; ver ROADMAP).

Handler real: ``src/mlops/handler.py``. O pacote de deploy precisaria incluir
``src/mlops/`` e ``model_artifacts/riskcredit-v3/`` (modo local) ou apontar
``INFERENCE_MODE=sagemaker`` para um endpoint com o modelo v3.
A Lambda v1 em produção (`lambda_function.py`) não foi alterada.
"""

from src.mlops.handler import lambda_handler  # noqa: F401
