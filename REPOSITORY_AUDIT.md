# FPL Strategist Repository Audit — 2026/27

## Repository reviewed
Current uploaded ZIP: `FPL-agent-main.zip`

## Executive assessment

The repository has a substantial quantitative foundation, but it is not yet a complete
FPL Strategist. The existing code is strongest in historical football modelling and
FPL truth/data normalization. The production strategy layer remains largely absent.

The existing Streamlit `app.py` already presents a useful dashboard/chat experience,
but it currently embeds strategy calculations and an external Gemini dependency
directly in the UI layer. It should eventually become a thin presentation layer.

## Completed / strong foundation

### Truth and data
- `fpl_truth.py` — official FPL API retrieval for bootstrap, fixtures, manager picks,
  manager history, manager details and player summaries.
- `player_data.py` — normalized player universe.
- `player_history.py` — player Gameweek history normalization.
- `fixture_data.py` — structured fixture normalization.
- `validation.py` — manager-picks validation.

### Historical football data
- `historical_team_data.py`
- `historical_team_state.py`
- `historical_player_data.py`
- `historical_prior.py`
- `walk_forward_validation.py`
- `walk_forward_data.py`

The walk-forward layer now carries both current-season point-in-time state and the
locked Historical Prior metadata.

### Football modelling
- `team_data.py`
- `team_strength.py`
- `fixture_model.py`
- `expected_goals_model.py`
- `expected_goals_evaluation.py`
- `expected_goals_calibration.py`

The expected-goals baseline is deliberately transparent and already has leakage-safe
walk-forward evaluation/calibration infrastructure.

## Partial / diagnostic

### Expected goals
Historical Prior is currently diagnostic-only. It has not yet been proven to improve
the expected-goals model and therefore should not be inserted into production xG
until the planned out-of-sample comparison is completed.

### Expected points
The repository does not yet contain a dedicated validated expected-FPL-points model.
The old `app.py` contains an embedded heuristic:
`form * 0.6 + xGI * 1.5`, multiplied by an FDR lookup. This should NOT be treated as
the production expected-points engine.

### App architecture
`app.py` currently contains:
- API retrieval
- state calculation
- expected-points heuristics
- league retrieval
- squad rendering
- chat persistence
- LLM prompting
- Gemini invocation

This is too much responsibility for a production architecture.

### Persistence / multi-user
The app currently uses GitHub Gist-style persistence and a hard-coded team ID.
The agreed multi-user/cloud state architecture is not yet implemented.

### News
The official FPL `news`, availability probability and status fields are available
through bootstrap data, but a dedicated auditable news/injury intelligence layer
does not yet exist.

## Missing production strategy layers

1. Expected-points engine with validated football inputs.
2. Squad optimizer / legal transfer search.
3. Transfer strategy engine.
4. Captaincy engine.
5. Chip optimization engine.
6. Rival/mini-league context engine.
7. Strategic state/memory layer.
8. Recommendation audit trail.
9. Proactive strategy cadence / decision snapshots.
10. Thin UI adapter that consumes structured strategy output.
11. Multi-user authentication and isolated manager state.
12. Cloud persistence abstraction.
13. External-news source abstraction with timestamps/confidence.
14. End-to-end strategy tests.

## Important architecture decision

The LLM should explain structured strategy results; it should not be the source of
truth for squad state, transfers, expected points, chips, ranks or fixture facts.

Target architecture:

Official FPL API
    -> Truth / validation
    -> Structured manager state
    -> Football models
    -> Expected points
    -> Strategy engines
    -> Auditable recommendation
    -> LLM explanation
    -> UI

## Batch created in this delivery

The accompanying implementation batch contains:

- `strategist_config.py`
- `manager_state.py`
- `fixture_utils.py`
- `expected_points.py`
- `transfer_engine.py`
- `captain_engine.py`
- `chip_engine.py`
- `rival_engine.py`
- `strategy_engine.py`
- corresponding unit tests

These files are intentionally additive: they do not overwrite the validated
historical/model files in the repository.

## Important limitation

This batch is a coherent V1 strategy foundation, not a claim that the complete
FPL Strategist is already production-ready. The expected-points layer explicitly
marks missing football probabilities as incomplete rather than fabricating them.
The chip engine is also a framework pending proper blank/double Gameweek opportunity
modelling.

## Recommended build order after this batch

1. Run all existing tests.
2. Run the new strategy-module tests.
3. Connect the validated xG layer to fixture-level player expected points.
4. Build player expected-minutes/start-probability validation.
5. Add legal full-squad transfer optimization.
6. Add blank/double Gameweek and chip opportunity model.
7. Add rival context without changing the universal team objective.
8. Add strategic memory and audit snapshots.
9. Refactor Streamlit app into UI-only orchestration.
10. Add cloud persistence/authentication.
11. End-to-end test the strategist against the real manager/team.
