PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS data_sources (
    source_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    base_url TEXT,
    notes TEXT,
    last_successful_pull_utc TEXT
);

CREATE TABLE IF NOT EXISTS competitions (
    competition_id TEXT PRIMARY KEY,
    competition_name TEXT NOT NULL,
    competition_code TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS seasons (
    season_id TEXT PRIMARY KEY,
    competition_id TEXT NOT NULL REFERENCES competitions(competition_id),
    season_name TEXT NOT NULL,
    UNIQUE(competition_id, season_name)
);

CREATE TABLE IF NOT EXISTS teams (
    team_id TEXT PRIMARY KEY,
    asa_team_id TEXT,
    fotmob_team_id TEXT,
    team_name TEXT NOT NULL,
    team_short_name TEXT,
    team_abbreviation TEXT,
    normalized_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS players (
    player_id TEXT PRIMARY KEY,
    asa_player_id TEXT,
    fotmob_player_id TEXT,
    player_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    birth_date TEXT,
    nationality TEXT,
    primary_position TEXT,
    position_group TEXT,
    is_goalkeeper INTEGER NOT NULL DEFAULT 0,
    is_synthetic INTEGER NOT NULL DEFAULT 0,
    CHECK (is_synthetic = 0)
);

CREATE TABLE IF NOT EXISTS matches (
    match_id TEXT PRIMARY KEY,
    asa_game_id TEXT,
    fotmob_match_id TEXT,
    season_id TEXT NOT NULL REFERENCES seasons(season_id),
    competition_id TEXT NOT NULL REFERENCES competitions(competition_id),
    match_date TEXT NOT NULL,
    match_datetime_utc TEXT,
    home_team_id TEXT NOT NULL REFERENCES teams(team_id),
    away_team_id TEXT NOT NULL REFERENCES teams(team_id),
    home_score INTEGER,
    away_score INTEGER,
    status TEXT NOT NULL,
    is_knockout INTEGER NOT NULL DEFAULT 0,
    expanded_minutes REAL,
    data_cutoff_date TEXT,
    UNIQUE(asa_game_id),
    UNIQUE(fotmob_match_id)
);

CREATE TABLE IF NOT EXISTS lineups (
    lineup_id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL REFERENCES matches(match_id),
    team_id TEXT NOT NULL REFERENCES teams(team_id),
    player_id TEXT NOT NULL REFERENCES players(player_id),
    is_starter INTEGER NOT NULL,
    shirt_number TEXT,
    position_code TEXT,
    formation TEXT,
    UNIQUE(match_id, player_id)
);

CREATE TABLE IF NOT EXISTS match_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL REFERENCES matches(match_id),
    team_id TEXT REFERENCES teams(team_id),
    player_id TEXT REFERENCES players(player_id),
    secondary_player_id TEXT REFERENCES players(player_id),
    event_type TEXT NOT NULL,
    clock_minute REAL NOT NULL,
    stoppage_minute REAL NOT NULL DEFAULT 0,
    normalized_minute REAL NOT NULL,
    home_score INTEGER,
    away_score INTEGER,
    payload_json TEXT,
    source TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_match_events_match ON match_events(match_id, normalized_minute);

CREATE TABLE IF NOT EXISTS substitutions (
    substitution_id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL REFERENCES matches(match_id),
    team_id TEXT NOT NULL REFERENCES teams(team_id),
    player_in_id TEXT NOT NULL REFERENCES players(player_id),
    player_out_id TEXT REFERENCES players(player_id),
    clock_minute REAL NOT NULL,
    stoppage_minute REAL NOT NULL DEFAULT 0,
    normalized_minute REAL NOT NULL,
    entry_score_for INTEGER,
    entry_score_against INTEGER,
    score_difference_at_entry INTEGER,
    is_home INTEGER NOT NULL,
    injured_player_out INTEGER NOT NULL DEFAULT 0,
    simultaneous_sub_count INTEGER NOT NULL DEFAULT 1,
    simultaneous_group_id TEXT,
    formation_before TEXT,
    formation_after TEXT,
    UNIQUE(match_id, team_id, player_in_id, normalized_minute)
);

CREATE TABLE IF NOT EXISTS player_match_intervals (
    interval_id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL REFERENCES matches(match_id),
    player_id TEXT NOT NULL REFERENCES players(player_id),
    team_id TEXT NOT NULL REFERENCES teams(team_id),
    opponent_id TEXT NOT NULL REFERENCES teams(team_id),
    role TEXT NOT NULL CHECK (role IN ('starter', 'substitute')),
    entry_minute REAL NOT NULL,
    exit_minute REAL NOT NULL,
    minutes_played REAL NOT NULL,
    is_home INTEGER NOT NULL,
    entry_score_for INTEGER,
    entry_score_against INTEGER,
    exit_score_for INTEGER,
    exit_score_against INTEGER,
    red_card_state TEXT,
    replaced_player_id TEXT REFERENCES players(player_id),
    simultaneous_sub_count INTEGER DEFAULT 1,
    data_quality_flags TEXT,
    UNIQUE(match_id, player_id, entry_minute),
    CHECK (exit_minute >= entry_minute),
    CHECK (minutes_played >= 0)
);

CREATE TABLE IF NOT EXISTS player_match_metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL REFERENCES matches(match_id),
    player_id TEXT NOT NULL REFERENCES players(player_id),
    team_id TEXT NOT NULL REFERENCES teams(team_id),
    minutes_played REAL,
    goals REAL,
    assists REAL,
    xgoals REAL,
    xassists REAL,
    shots REAL,
    key_passes REAL,
    goals_added_total REAL,
    gplus_shooting REAL,
    gplus_passing REAL,
    gplus_receiving REAL,
    gplus_dribbling REAL,
    gplus_interrupting REAL,
    gplus_fouling REAL,
    fotmob_xg REAL,
    fotmob_xa REAL,
    defensive_actions REAL,
    source TEXT NOT NULL,
    UNIQUE(match_id, player_id, source)
);

CREATE TABLE IF NOT EXISTS team_match_windows (
    window_id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL REFERENCES matches(match_id),
    team_id TEXT NOT NULL REFERENCES teams(team_id),
    window_type TEXT NOT NULL,
    start_minute REAL NOT NULL,
    end_minute REAL NOT NULL,
    xg_for REAL,
    xg_against REAL,
    xg_diff REAL,
    goals_for REAL,
    goals_against REAL,
    shots_for REAL,
    shots_against REAL,
    UNIQUE(match_id, team_id, window_type, start_minute, end_minute)
);

CREATE TABLE IF NOT EXISTS substitute_appearances (
    appearance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL REFERENCES matches(match_id),
    player_id TEXT NOT NULL REFERENCES players(player_id),
    team_id TEXT NOT NULL REFERENCES teams(team_id),
    opponent_id TEXT NOT NULL REFERENCES teams(team_id),
    season TEXT NOT NULL,
    competition TEXT NOT NULL,
    match_date TEXT NOT NULL,
    home_away TEXT NOT NULL,
    entry_minute REAL NOT NULL,
    normalized_entry_minute REAL NOT NULL,
    exit_minute REAL NOT NULL,
    substitute_minutes REAL NOT NULL,
    entry_score_for INTEGER,
    entry_score_against INTEGER,
    score_difference_at_entry INTEGER,
    score_state_at_entry TEXT,
    score_state_simple TEXT,
    final_score_for INTEGER,
    final_score_against INTEGER,
    red_card_state TEXT,
    simultaneous_sub_count INTEGER,
    entering_position TEXT,
    position_group TEXT,
    replaced_player_id TEXT,
    replaced_player_position TEXT,
    formation_before TEXT,
    formation_after TEXT,
    team_strength REAL,
    opponent_strength REAL,
    entry_timing_category TEXT,
    tactical_situation TEXT,
    pre_entry_xg_diff_per90 REAL,
    post_entry_xg_diff_per90 REAL,
    post_entry_change REAL,
    player_gplus REAL,
    player_gplus_per96 REAL,
    player_xg REAL,
    player_xa REAL,
    player_shots REAL,
    positive_appearance INTEGER,
    adjusted_post_entry_residual REAL,
    data_quality_flags TEXT,
    UNIQUE(match_id, player_id)
);

CREATE TABLE IF NOT EXISTS starter_appearances (
    appearance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT NOT NULL REFERENCES matches(match_id),
    player_id TEXT NOT NULL REFERENCES players(player_id),
    team_id TEXT NOT NULL REFERENCES teams(team_id),
    opponent_id TEXT NOT NULL REFERENCES teams(team_id),
    season TEXT NOT NULL,
    match_date TEXT NOT NULL,
    home_away TEXT NOT NULL,
    starting_minutes REAL NOT NULL,
    position_group TEXT,
    player_gplus REAL,
    player_gplus_per96 REAL,
    player_xg REAL,
    player_xa REAL,
    UNIQUE(match_id, player_id)
);

CREATE TABLE IF NOT EXISTS player_context_splits (
    split_id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id TEXT NOT NULL REFERENCES players(player_id),
    evaluation_period TEXT NOT NULL,
    split_type TEXT NOT NULL,
    split_value TEXT NOT NULL,
    appearances INTEGER,
    minutes REAL,
    mean_gplus_per96 REAL,
    mean_adjusted_team_impact REAL,
    positive_rate REAL,
    UNIQUE(player_id, evaluation_period, split_type, split_value)
);

CREATE TABLE IF NOT EXISTS player_bench_scores (
    score_id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id TEXT NOT NULL REFERENCES players(player_id),
    evaluation_period TEXT NOT NULL,
    position_group TEXT NOT NULL,
    club_team_id TEXT REFERENCES teams(team_id),
    age REAL,
    substitute_appearances INTEGER NOT NULL,
    substitute_minutes REAL NOT NULL,
    median_entry_minute REAL,
    starts INTEGER,
    starting_minutes REAL,
    substitute_sporting_impact REAL,
    adjusted_team_impact_after_entry REAL,
    positive_impact_frequency REAL,
    positive_impact_frequency_percentile REAL,
    substitute_advantage REAL,
    substitute_advantage_percentile REAL,
    bench_impact_score REAL,
    overall_rank INTEGER,
    position_rank INTEGER,
    data_confidence TEXT,
    model_uncertainty REAL,
    classification_primary TEXT,
    classification_tags TEXT,
    components_missing TEXT,
    observed_gplus_per96 REAL,
    adjusted_gplus_per96 REAL,
    team_impact_point REAL,
    team_impact_ci_low REAL,
    team_impact_ci_high REAL,
    model_version TEXT NOT NULL,
    data_version TEXT NOT NULL,
    calculation_timestamp TEXT NOT NULL,
    source_cutoff_dates TEXT NOT NULL,
    UNIQUE(player_id, evaluation_period, model_version)
);

CREATE TABLE IF NOT EXISTS player_substitute_advantage (
    adv_id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id TEXT NOT NULL REFERENCES players(player_id),
    evaluation_period TEXT NOT NULL,
    adjusted_substitute_rate REAL,
    adjusted_starter_rate REAL,
    substitute_advantage_raw REAL,
    substitute_advantage_adjusted REAL,
    advantage_percentile REAL,
    ci_low REAL,
    ci_high REAL,
    interpretation TEXT,
    available INTEGER NOT NULL,
    model_version TEXT NOT NULL,
    UNIQUE(player_id, evaluation_period, model_version)
);

CREATE TABLE IF NOT EXISTS model_runs (
    model_run_id TEXT PRIMARY KEY,
    model_version TEXT NOT NULL,
    data_version TEXT NOT NULL,
    evaluation_period TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    parameters_json TEXT,
    status TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    pipeline_run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    stages_json TEXT,
    data_cutoff_date TEXT,
    git_commit TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS validation_results (
    validation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_run_id TEXT REFERENCES model_runs(model_run_id),
    test_name TEXT NOT NULL,
    component TEXT NOT NULL,
    metric_name TEXT,
    metric_value REAL,
    passed INTEGER,
    details_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bench_scores_period_rank
    ON player_bench_scores(evaluation_period, overall_rank);
CREATE INDEX IF NOT EXISTS idx_sub_apps_player
    ON substitute_appearances(player_id, season);
CREATE INDEX IF NOT EXISTS idx_players_name
    ON players(normalized_name);