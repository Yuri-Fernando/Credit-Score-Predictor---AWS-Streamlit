#!/usr/bin/env bash
# Guard-rail de custo (plano §5.1/5.3): único caminho suportado para operar
# infra/terraform nesta fase do projeto é fmt/validate/plan — nunca apply/destroy
# contra uma conta AWS real. Mesmo padrão usado no ArgusAI e no Enterprise Cloud
# Automation Platform desta mesma auditoria.
#
# Uso:
#   scripts/terraform_guard.sh fmt
#   scripts/terraform_guard.sh validate
#   scripts/terraform_guard.sh plan        # dry-run; precisa de credenciais AWS válidas
#   scripts/terraform_guard.sh apply       # SEMPRE bloqueado por este script
#
# Para destravar `apply`/`destroy` de propósito (ex.: numa conta de staging com
# orçamento e alertas configurados, decisão humana explícita), é preciso as DUAS
# confirmações abaixo — nenhuma delas é persistida neste repositório:
#   export TF_GUARD_ALLOW_APPLY=yes-eu-entendo-o-custo
#   scripts/terraform_guard.sh apply -- -auto-approve=false
set -euo pipefail

cmd="${1:-}"
shift || true

cd "$(dirname "${BASH_SOURCE[0]}")/../infra/terraform"

case "$cmd" in
  fmt)
    terraform fmt -check -recursive "$@"
    ;;
  validate)
    terraform init -backend=false -input=false -upgrade=false
    terraform validate "$@"
    ;;
  plan)
    terraform init -backend=false -input=false -upgrade=false
    terraform plan -input=false "$@"
    ;;
  apply|destroy)
    if [ "${TF_GUARD_ALLOW_APPLY:-}" != "yes-eu-entendo-o-custo" ]; then
      echo "BLOQUEADO: '$cmd' real contra a AWS não é suportado por este script sem" >&2
      echo "TF_GUARD_ALLOW_APPLY=yes-eu-entendo-o-custo definido explicitamente." >&2
      echo "Decisão do dono do projeto: infra pausada por custo (ver README.md/ROADMAP.md)." >&2
      exit 1
    fi
    echo "AVISO: executando '$cmd' real contra uma conta AWS. Ctrl+C em 5s para cancelar." >&2
    sleep 5
    terraform init -backend=false -input=false -upgrade=false
    terraform "$cmd" "$@"
    ;;
  *)
    echo "uso: $0 {fmt|validate|plan|apply|destroy} [args do terraform]" >&2
    exit 2
    ;;
esac
