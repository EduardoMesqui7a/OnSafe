# OnSafe

Backend em Python para monitoramento de cameras IP com deteccao de EPI, tracking por pessoa e geracao automatica de evidencias e relatorios.

## Principios

- captura desacoplada da inferencia
- politica de latest frame wins para evitar atraso crescente
- decisao conservadora para reduzir falso positivo
- evidencias e relatorios gerados fora do caminho critico

## Estrutura principal

- `app/core`: configuracoes, enums e DTOs
- `app/storage`: banco SQLite, modelos e repositorios
- `app/services`: contratos de alto nivel para a futura UI Streamlit
- `app/pipeline`: captura, tracking, conformidade, evidencias e orquestracao
- `app/reporting`: geracao de HTML/PDF
- `app/scripts`: scripts operacionais

## Fluxo esperado

1. Registrar cameras com `CameraService`
2. Testar conexao
3. Iniciar monitoramento com `MonitoringService`
4. Consumir status, snapshots, tracks e eventos pelo contrato em `app/integrations/streamlit_contracts.py`

## Observacoes

- A camada Streamlit nao esta implementada aqui por decisao de escopo.
- `WeasyPrint` e `Ultralytics` sao opcionais em runtime. O backend continua operacional com fallback quando esses pacotes nao estiverem disponiveis.

## Exemplo rapido

```python
from app.core.config import get_settings
from app.storage.database import init_database
from app.integrations.streamlit_contracts import OnSafeBackend

settings = get_settings()
init_database(settings.database_url)
backend = OnSafeBackend(settings)
```
