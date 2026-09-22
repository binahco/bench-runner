# bench-runner

> **Semana:** 5 · **Core:** `llm-dev-core` 0.5.0

## Problema

Los prompts de los consumidores de `llm-dev-core` son piezas de comportamiento: si el
modelo tiende a cambio o el prompt se edita, la salida derivada puede degradarse sin que
nadie se entere hasta que llega a producción. `bench-runner` convierte los tests de un
prompt en datasets de eval y decide —con umbral y presupuesto— si una corrida es una
regresión (exit 1), está en verde (exit 0) o su dataset es inválido (exit 2).

## Demo

```
$ bench-runner --replay cassettes/ --mode full
{ "total": 4, "passed": 4, "pass_rate": 1.0, "threshold_ok": true, "cost_usd": "0.0" }
$ echo $?
0
```

El propio prompt de `bench-runner` (`regression-report-generator`) nace evaluado: es el
dogfood del seed de `test-kit`.

## Arquitectura

```
evals/*.jsonl ──► test-kit (dataset + criterios + umbral) ──► reporte + exit code
       ▲                    │
       │                judge (per-consumidor)
       │                    │
prompts/*.md ──► llm-client (render + validación + retry/reparación)
                      │
                 ReplayProvider (CI determinista) · OpenCodeCLI (seed/grabación)
```

El `judge` es un callable `EvalCase → CompletionResult` que el consumidor aporta: el
runner de `test-kit` es agnóstico del transporte. CI usa `--replay cassettes/` para no
tocar jamás un LLM en pruebas (D4). La grabación real es una acción explícita
(`scripts/record_tape_opencode.py`).

## Recicla de

| Módulo del core | Qué aporta |
|---|---|
| `llm-client` | Llamadas LLM, retry, streaming, telemetría, ReplayProvider (D4) |
| `schema-validate` | Salida validada (`regression-report-v1`) antes de entrar al dominio |
| `test-kit` | Datasets de caso (tres criterios), runner, umbrales y presupuestos (§8.1) |

## Limitaciones

- Criterios deterministas (`deterministic_match`, `json_match`, `schema_match`); el
  juicio semántico LLM-as-judge es un hook pendiente (ADR-0004).
- El dataset congelado es un snapshot del baseline válido (4 casos); re-baseline es una
  acción deliberada, no automática.
- `modo: texto` no se valida contra schema a propósito: el veredicto en línea es
  `deterministic_match` puro.

## Roadmap

- Sem 6: retrofit evaluado de los prompts de `commit-cli`, `release-scribe` y `sec-check`.
- Ampliar dataset congelado a 5+ casos de regresión real.
- Decidir criterios no-deterministas (LLM-as-judge) contra un golden set etiquetado.