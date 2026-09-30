-- FPL Strategist SQLite schema.
-- Domain schema only: application/business logic must access this through the
-- persistence/repository layer rather than embedding SQL in strategy modules.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seasons (
    id INTEGER PRIMARY KEY,
    season_code TEXT NOT NULL UNIQUE,
    start_date TEXT,
    end_date TEXT,
    status TEXT,
    is_current INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gameweeks (
    id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL REFERENCES seasons(id),
    gameweek INTEGER NOT NULL,
    name TEXT,
    deadline_time TEXT,
    finished INTEGER NOT NULL DEFAULT 0,
    data_checked INTEGER NOT NULL DEFAULT 0,
    is_current INTEGER NOT NULL DEFAULT 0,
    is_next INTEGER NOT NULL DEFAULT 0,
    is_previous INTEGER NOT NULL DEFAULT 0,
    UNIQUE(season_id, gameweek)
);

CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY,
    fpl_team_id INTEGER NOT NULL UNIQUE,
    name TEXT NOT NULL,
    short_name TEXT,
    code INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS team_snapshots (
    id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL REFERENCES seasons(id),
    team_id INTEGER NOT NULL REFERENCES teams(id),
    snapshot_at TEXT NOT NULL,
    ingestion_run_id INTEGER,
    strength REAL,
    strength_overall_home REAL,
    strength_overall_away REAL,
    strength_attack_home REAL,
    strength_attack_away REAL,
    strength_defence_home REAL,
    strength_defence_away REAL,
    UNIQUE(team_id, season_id, snapshot_at)
);

CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY,
    fpl_player_id INTEGER NOT NULL UNIQUE,
    first_name TEXT,
    second_name TEXT,
    web_name TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS player_snapshots (
    id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL REFERENCES seasons(id),
    player_id INTEGER NOT NULL REFERENCES players(id),
    snapshot_at TEXT NOT NULL,
    ingestion_run_id INTEGER,
    team_id INTEGER REFERENCES teams(id),
    position_id INTEGER,
    position TEXT,
    price REAL,
    form REAL,
    total_points INTEGER,
    event_points INTEGER,
    points_per_game REAL,
    selected_by_percent REAL,
    minutes INTEGER,
    starts INTEGER,
    goals_scored INTEGER,
    assists INTEGER,
    clean_sheets INTEGER,
    expected_goals REAL,
    expected_assists REAL,
    expected_goal_involvements REAL,
    expected_goals_conceded REAL,
    bonus INTEGER,
    bps INTEGER,
    defensive_contribution INTEGER,
    influence REAL,
    creativity REAL,
    threat REAL,
    ict_index REAL,
    status TEXT,
    chance_of_playing_this_round INTEGER,
    chance_of_playing_next_round INTEGER,
    news TEXT,
    news_added TEXT,
    transfers_in INTEGER,
    transfers_out INTEGER,
    transfers_in_event INTEGER,
    transfers_out_event INTEGER,
    can_select INTEGER,
    can_transact INTEGER,
    UNIQUE(player_id, season_id, snapshot_at)
);

CREATE TABLE IF NOT EXISTS fixtures (
    id INTEGER PRIMARY KEY,
    fpl_fixture_id INTEGER NOT NULL UNIQUE,
    season_id INTEGER NOT NULL REFERENCES seasons(id),
    gameweek_id INTEGER REFERENCES gameweeks(id),
    home_team_id INTEGER NOT NULL REFERENCES teams(id),
    away_team_id INTEGER NOT NULL REFERENCES teams(id),
    kickoff_time TEXT,
    started INTEGER NOT NULL DEFAULT 0,
    finished INTEGER NOT NULL DEFAULT 0,
    home_score INTEGER,
    away_score INTEGER,
    home_difficulty INTEGER,
    away_difficulty INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS current_player_gameweek_stats (
    id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL REFERENCES seasons(id),
    gameweek_id INTEGER REFERENCES gameweeks(id),
    player_id INTEGER NOT NULL REFERENCES players(id),
    fixture_id INTEGER NOT NULL REFERENCES fixtures(id),
    opponent_team_id INTEGER REFERENCES teams(id),
    was_home INTEGER,
    kickoff_time TEXT,
    minutes INTEGER,
    starts INTEGER,
    total_points INTEGER,
    goals_scored INTEGER,
    assists INTEGER,
    clean_sheets INTEGER,
    goals_conceded INTEGER,
    own_goals INTEGER,
    penalties_saved INTEGER,
    penalties_missed INTEGER,
    saves INTEGER,
    bonus INTEGER,
    bps INTEGER,
    yellow_cards INTEGER,
    red_cards INTEGER,
    expected_goals REAL,
    expected_assists REAL,
    expected_goal_involvements REAL,
    expected_goals_conceded REAL,
    influence REAL,
    creativity REAL,
    threat REAL,
    ict_index REAL,
    clearances_blocks_interceptions INTEGER,
    recoveries INTEGER,
    tackles INTEGER,
    defensive_contribution INTEGER,
    value REAL,
    selected INTEGER,
    transfers_balance INTEGER,
    transfers_in INTEGER,
    transfers_out INTEGER,
    ingestion_run_id INTEGER,
    UNIQUE(season_id, player_id, fixture_id)
);

CREATE TABLE IF NOT EXISTS historical_player_gameweek_stats (
    id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL REFERENCES seasons(id),
    gameweek INTEGER NOT NULL,
    player_id INTEGER NOT NULL REFERENCES players(id),
    fixture_id INTEGER,
    opponent_team_id INTEGER REFERENCES teams(id),
    was_home INTEGER,
    kickoff_time TEXT,
    minutes INTEGER,
    starts INTEGER,
    total_points INTEGER,
    goals_scored INTEGER,
    assists INTEGER,
    clean_sheets INTEGER,
    goals_conceded INTEGER,
    own_goals INTEGER,
    penalties_saved INTEGER,
    penalties_missed INTEGER,
    saves INTEGER,
    bonus INTEGER,
    bps INTEGER,
    yellow_cards INTEGER,
    red_cards INTEGER,
    expected_goals REAL,
    expected_assists REAL,
    expected_goal_involvements REAL,
    expected_goals_conceded REAL,
    influence REAL,
    creativity REAL,
    threat REAL,
    ict_index REAL,
    clearances_blocks_interceptions INTEGER,
    recoveries INTEGER,
    tackles INTEGER,
    defensive_contribution INTEGER,
    value REAL,
    selected INTEGER,
    transfers_balance INTEGER,
    transfers_in INTEGER,
    transfers_out INTEGER,
    source_dataset TEXT,
    source_record_key TEXT,
    ingestion_run_id INTEGER,
    UNIQUE(season_id, player_id, fixture_id)
);

CREATE TABLE IF NOT EXISTS historical_matches (
    id INTEGER PRIMARY KEY,
    match_id TEXT NOT NULL UNIQUE,
    season_id INTEGER NOT NULL REFERENCES seasons(id),
    match_date TEXT,
    kickoff_datetime TEXT,
    home_team_name TEXT NOT NULL,
    away_team_name TEXT NOT NULL,
    home_goals INTEGER,
    away_goals INTEGER,
    result TEXT,
    home_ht_goals INTEGER,
    away_ht_goals INTEGER,
    ht_result TEXT,
    home_shots INTEGER,
    away_shots INTEGER,
    home_shots_on_target INTEGER,
    away_shots_on_target INTEGER,
    home_corners INTEGER,
    away_corners INTEGER,
    home_fouls INTEGER,
    away_fouls INTEGER,
    home_yellow_cards INTEGER,
    away_yellow_cards INTEGER,
    home_red_cards INTEGER,
    away_red_cards INTEGER,
    source_dataset TEXT,
    source_record_key TEXT,
    ingestion_run_id INTEGER
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    external_user_key TEXT NOT NULL UNIQUE,
    display_name TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS managers (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    fpl_manager_id INTEGER NOT NULL UNIQUE,
    manager_name TEXT,
    team_name TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS manager_gameweek_state (
    id INTEGER PRIMARY KEY,
    manager_id INTEGER NOT NULL REFERENCES managers(id),
    season_id INTEGER NOT NULL REFERENCES seasons(id),
    gameweek_id INTEGER NOT NULL REFERENCES gameweeks(id),
    points INTEGER,
    total_points INTEGER,
    overall_rank INTEGER,
    rank INTEGER,
    bank REAL,
    team_value REAL,
    event_transfers INTEGER,
    event_transfers_cost INTEGER,
    points_on_bench INTEGER,
    source_timestamp TEXT,
    ingestion_run_id INTEGER,
    UNIQUE(manager_id, season_id, gameweek_id)
);

CREATE TABLE IF NOT EXISTS manager_picks (
    id INTEGER PRIMARY KEY,
    manager_id INTEGER NOT NULL REFERENCES managers(id),
    season_id INTEGER NOT NULL REFERENCES seasons(id),
    gameweek_id INTEGER NOT NULL REFERENCES gameweeks(id),
    player_id INTEGER NOT NULL REFERENCES players(id),
    position INTEGER,
    multiplier INTEGER,
    is_captain INTEGER NOT NULL DEFAULT 0,
    is_vice_captain INTEGER NOT NULL DEFAULT 0,
    purchase_price REAL,
    ingestion_run_id INTEGER,
    UNIQUE(manager_id, season_id, gameweek_id, player_id)
);

CREATE TABLE IF NOT EXISTS manager_transfers (
    id INTEGER PRIMARY KEY,
    manager_id INTEGER NOT NULL REFERENCES managers(id),
    season_id INTEGER NOT NULL REFERENCES seasons(id),
    gameweek_id INTEGER NOT NULL REFERENCES gameweeks(id),
    transfer_timestamp TEXT,
    player_in_id INTEGER REFERENCES players(id),
    player_out_id INTEGER REFERENCES players(id),
    cost INTEGER,
    external_transfer_id TEXT,
    ingestion_run_id INTEGER
);

CREATE TABLE IF NOT EXISTS manager_chips (
    id INTEGER PRIMARY KEY,
    manager_id INTEGER NOT NULL REFERENCES managers(id),
    season_id INTEGER NOT NULL REFERENCES seasons(id),
    chip_type TEXT NOT NULL,
    gameweek_id INTEGER REFERENCES gameweeks(id),
    used_at TEXT,
    UNIQUE(manager_id, season_id, chip_type)
);

CREATE TABLE IF NOT EXISTS leagues (
    id INTEGER PRIMARY KEY,
    fpl_league_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL REFERENCES seasons(id),
    name TEXT,
    league_type TEXT,
    UNIQUE(fpl_league_id, season_id)
);

CREATE TABLE IF NOT EXISTS league_members (
    id INTEGER PRIMARY KEY,
    league_id INTEGER NOT NULL REFERENCES leagues(id),
    manager_id INTEGER NOT NULL REFERENCES managers(id),
    UNIQUE(league_id, manager_id)
);

CREATE TABLE IF NOT EXISTS league_standings (
    id INTEGER PRIMARY KEY,
    league_id INTEGER NOT NULL REFERENCES leagues(id),
    manager_id INTEGER NOT NULL REFERENCES managers(id),
    season_id INTEGER NOT NULL REFERENCES seasons(id),
    gameweek_id INTEGER NOT NULL REFERENCES gameweeks(id),
    rank INTEGER,
    total_points INTEGER,
    last_rank INTEGER,
    rank_change INTEGER,
    ingestion_run_id INTEGER,
    UNIQUE(league_id, season_id, gameweek_id, manager_id)
);

CREATE TABLE IF NOT EXISTS rival_squad_snapshots (
    id INTEGER PRIMARY KEY,
    league_id INTEGER NOT NULL REFERENCES leagues(id),
    manager_id INTEGER NOT NULL REFERENCES managers(id),
    season_id INTEGER NOT NULL REFERENCES seasons(id),
    gameweek_id INTEGER NOT NULL REFERENCES gameweeks(id),
    player_id INTEGER NOT NULL REFERENCES players(id),
    position INTEGER,
    is_captain INTEGER NOT NULL DEFAULT 0,
    is_vice_captain INTEGER NOT NULL DEFAULT 0,
    multiplier INTEGER,
    ingestion_run_id INTEGER,
    UNIQUE(league_id, manager_id, season_id, gameweek_id, player_id)
);

CREATE TABLE IF NOT EXISTS player_availability (
    id INTEGER PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id),
    season_id INTEGER NOT NULL REFERENCES seasons(id),
    observed_at TEXT NOT NULL,
    status TEXT,
    chance_of_playing INTEGER,
    news TEXT,
    news_added TEXT,
    source TEXT,
    source_url TEXT,
    ingestion_run_id INTEGER
);

CREATE TABLE IF NOT EXISTS rules_versions (
    id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL REFERENCES seasons(id),
    version TEXT NOT NULL,
    effective_from TEXT,
    effective_to TEXT,
    is_active INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(season_id, version)
);

CREATE TABLE IF NOT EXISTS rules_payload (
    id INTEGER PRIMARY KEY,
    rules_version_id INTEGER NOT NULL REFERENCES rules_versions(id),
    rule_key TEXT NOT NULL,
    rule_value TEXT,
    description TEXT,
    UNIQUE(rules_version_id, rule_key)
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id INTEGER PRIMARY KEY,
    source_system TEXT NOT NULL,
    source_type TEXT NOT NULL,
    endpoint_or_file TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    source_retrieved_at TEXT,
    status TEXT NOT NULL,
    records_received INTEGER,
    records_written INTEGER,
    records_rejected INTEGER,
    content_hash TEXT,
    validation_status TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dataset_freshness (
    id INTEGER PRIMARY KEY,
    dataset_name TEXT NOT NULL UNIQUE,
    last_successful_ingestion_id INTEGER REFERENCES ingestion_runs(id),
    last_attempted_ingestion_id INTEGER REFERENCES ingestion_runs(id),
    last_successful_refresh_at TEXT,
    last_attempted_refresh_at TEXT,
    freshness_threshold_seconds INTEGER,
    freshness_status TEXT,
    current_gameweek_id INTEGER REFERENCES gameweeks(id),
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS player_predictions (
    id INTEGER PRIMARY KEY,
    season_id INTEGER NOT NULL REFERENCES seasons(id),
    gameweek_id INTEGER NOT NULL REFERENCES gameweeks(id),
    player_id INTEGER NOT NULL REFERENCES players(id),
    model_version TEXT NOT NULL,
    predicted_at TEXT NOT NULL,
    expected_points REAL,
    expected_minutes REAL,
    expected_goals REAL,
    expected_assists REAL,
    expected_clean_sheet REAL,
    expected_bonus REAL,
    data_complete INTEGER NOT NULL DEFAULT 0,
    warnings TEXT,
    model_inputs_hash TEXT,
    UNIQUE(season_id, gameweek_id, player_id, model_version)
);

CREATE TABLE IF NOT EXISTS prediction_outcomes (
    id INTEGER PRIMARY KEY,
    prediction_id INTEGER NOT NULL REFERENCES player_predictions(id),
    actual_points REAL,
    actual_minutes REAL,
    actual_goals REAL,
    actual_assists REAL,
    evaluated_at TEXT NOT NULL,
    evaluation_version TEXT,
    error_points REAL
);

CREATE TABLE IF NOT EXISTS strategy_memory (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    manager_id INTEGER NOT NULL REFERENCES managers(id),
    memory_type TEXT NOT NULL,
    memory_key TEXT NOT NULL,
    memory_value TEXT,
    confidence REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT,
    UNIQUE(manager_id, memory_type, memory_key)
);

CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    manager_id INTEGER NOT NULL REFERENCES managers(id),
    season_id INTEGER NOT NULL REFERENCES seasons(id),
    gameweek_id INTEGER NOT NULL REFERENCES gameweeks(id),
    recommendation_type TEXT NOT NULL,
    recommendation_status TEXT,
    recommendation_text TEXT,
    structured_payload TEXT,
    generated_at TEXT NOT NULL,
    model_version TEXT
);

CREATE TABLE IF NOT EXISTS recommendation_audits (
    id INTEGER PRIMARY KEY,
    recommendation_id INTEGER NOT NULL REFERENCES recommendations(id),
    data_snapshot_at TEXT NOT NULL,
    evidence_payload TEXT,
    input_data_hash TEXT,
    data_complete INTEGER NOT NULL DEFAULT 0,
    warnings TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recommendation_outcomes (
    id INTEGER PRIMARY KEY,
    recommendation_id INTEGER NOT NULL REFERENCES recommendations(id),
    evaluated_at TEXT NOT NULL,
    actual_result TEXT,
    outcome_payload TEXT
);

CREATE TABLE IF NOT EXISTS data_lineage (
    id INTEGER PRIMARY KEY,
    source_system TEXT NOT NULL,
    source_endpoint TEXT,
    source_entity TEXT,
    source_field TEXT,
    target_entity TEXT NOT NULL,
    target_field TEXT NOT NULL,
    transformation TEXT,
    mapping_type TEXT,
    mapping_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    effective_from TEXT,
    effective_to TEXT,
    description TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_player_snapshots_player_season_snapshot
    ON player_snapshots(player_id, season_id, snapshot_at);
CREATE INDEX IF NOT EXISTS idx_current_player_gw_stats_season_gw_player
    ON current_player_gameweek_stats(season_id, gameweek_id, player_id);
CREATE INDEX IF NOT EXISTS idx_historical_player_gw_stats_season_player_gw
    ON historical_player_gameweek_stats(season_id, player_id, gameweek);
CREATE INDEX IF NOT EXISTS idx_fixtures_season_gameweek
    ON fixtures(season_id, gameweek_id);
CREATE INDEX IF NOT EXISTS idx_fixtures_home_team_kickoff
    ON fixtures(home_team_id, kickoff_time);
CREATE INDEX IF NOT EXISTS idx_fixtures_away_team_kickoff
    ON fixtures(away_team_id, kickoff_time);
CREATE INDEX IF NOT EXISTS idx_manager_gameweek_state_manager_season_gw
    ON manager_gameweek_state(manager_id, season_id, gameweek_id);
CREATE INDEX IF NOT EXISTS idx_manager_picks_manager_season_gw
    ON manager_picks(manager_id, season_id, gameweek_id);
CREATE INDEX IF NOT EXISTS idx_league_standings_league_season_gw
    ON league_standings(league_id, season_id, gameweek_id);
CREATE INDEX IF NOT EXISTS idx_rival_squad_snapshots_league_season_gw
    ON rival_squad_snapshots(league_id, season_id, gameweek_id);
CREATE INDEX IF NOT EXISTS idx_player_predictions_season_gw_player
    ON player_predictions(season_id, gameweek_id, player_id);
CREATE INDEX IF NOT EXISTS idx_ingestion_runs_source_retrieved
    ON ingestion_runs(source_system, source_retrieved_at);
CREATE INDEX IF NOT EXISTS idx_dataset_freshness_status
    ON dataset_freshness(freshness_status);

INSERT OR IGNORE INTO schema_migrations(version, applied_at, description)
VALUES (1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), 'Initial FPL Strategist domain schema');
