def grant_referee(client, headers, tournament_id, user_id, actor='organizer'):
    return client.post(
        f'/api/v1/tournaments/{tournament_id}/referees',
        headers=headers(actor),
        json={'user_id': user_id},
    )


def admin_grant_referee(client, headers, tournament_id, user_id, scope_type='TOURNAMENT'):
    return client.post(
        '/api/v1/admin/role-assignments',
        headers=headers('admin'),
        json={
            'user_id': user_id,
            'role': 'REFEREE',
            'scope_type': scope_type,
            'scope_id': tournament_id if scope_type == 'TOURNAMENT' else None,
        },
    )
