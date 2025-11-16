# -*- coding: utf-8 -*-

def post_init_hook(cr, registry):
    """Post-installation hook"""
    # Create default dynamic users for existing users
    env = registry['res.users'].env(cr, 1)
    
    # Get all active users
    users = env['res.users'].search([('active', '=', True)])
    
    for user in users:
        # Check if dynamic user already exists
        existing_dynamic_user = env['dynamic.user'].search([
            ('user_id', '=', user.id)
        ])
        
        if not existing_dynamic_user:
            # Create dynamic user
            env['dynamic.user'].create({
                'name': user.name,
                'user_id': user.id,
                'approval_capacity': 'unlimited',
                'current_status': 'available',
                'email_notifications': True,
                'push_notifications': True,
            })


def uninstall_hook(cr, registry):
    """Pre-uninstallation hook"""
    # Clean up any custom data if needed
    pass
