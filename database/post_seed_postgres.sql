SELECT setval(pg_get_serial_sequence('roles', 'role_id'), COALESCE((SELECT MAX(role_id) FROM roles), 1));
SELECT setval(pg_get_serial_sequence('users', 'user_id'), COALESCE((SELECT MAX(user_id) FROM users), 1));
SELECT setval(pg_get_serial_sequence('teams', 'team_id'), COALESCE((SELECT MAX(team_id) FROM teams), 1));
SELECT setval(pg_get_serial_sequence('team_memberships', 'membership_id'), COALESCE((SELECT MAX(membership_id) FROM team_memberships), 1));
SELECT setval(pg_get_serial_sequence('tournaments', 'tournament_id'), COALESCE((SELECT MAX(tournament_id) FROM tournaments), 1));
SELECT setval(pg_get_serial_sequence('tournament_rosters', 'roster_id'), COALESCE((SELECT MAX(roster_id) FROM tournament_rosters), 1));
SELECT setval(pg_get_serial_sequence('stages', 'stage_id'), COALESCE((SELECT MAX(stage_id) FROM stages), 1));
SELECT setval(pg_get_serial_sequence('matches', 'match_id'), COALESCE((SELECT MAX(match_id) FROM matches), 1));
