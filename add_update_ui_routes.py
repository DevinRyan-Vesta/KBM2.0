#!/usr/bin/env python3
"""Add system update UI routes to app_admin"""

routes_addition = '''

@app_admin_bp.route('/admin/system/updates')
@login_required
@app_admin_required
@root_domain_only
def system_updates():
    """
    System updates page - view current version and check for updates.
    """
    from utilities.system_update import update_manager

    current_version = update_manager.get_current_version()
    containers = update_manager.get_container_status()

    return render_template('app_admin/system_updates.html',
                         current_version=current_version,
                         containers=containers)


@app_admin_bp.route('/admin/system/check-updates')
@login_required
@app_admin_required
@root_domain_only
def check_updates():
    """
    Check for available updates (AJAX endpoint).
    """
    from utilities.system_update import update_manager

    result = update_manager.check_for_updates()
    return jsonify(result)


@app_admin_bp.route('/admin/system/update', methods=['POST'])
@login_required
@app_admin_required
@root_domain_only
def perform_update():
    """
    Perform system update.
    """
    from utilities.system_update import update_manager

    rebuild = request.form.get('rebuild') == 'true'
    result = update_manager.perform_update(rebuild=rebuild)

    return jsonify(result)


@app_admin_bp.route('/admin/system/logs')
@login_required
@app_admin_required
@root_domain_only
def system_logs():
    """
    Get system logs (AJAX endpoint).
    """
    from utilities.system_update import update_manager

    lines = request.args.get('lines', 50, type=int)
    logs = update_manager.get_logs(lines=lines)

    return jsonify({"logs": logs})


@app_admin_bp.route('/admin/system/containers')
@login_required
@app_admin_required
@root_domain_only
def container_status():
    """
    Get container status (AJAX endpoint).
    """
    from utilities.system_update import update_manager

    containers = update_manager.get_container_status()
    return jsonify({"containers": containers})


@app_admin_bp.route('/admin/system/restart', methods=['POST'])
@login_required
@app_admin_required
@root_domain_only
def restart_system():
    """
    Restart Docker containers.
    """
    from utilities.system_update import update_manager

    success, message = update_manager.restart_containers()
    return jsonify({"success": success, "message": message})
'''

# Read the routes file
routes_path = "app_admin/routes.py"
with open(routes_path, 'r', encoding='utf-8') as f:
    routes_content = f.read()

# Check if system update routes already exist
if 'system_updates' not in routes_content:
    # Append to the end
    with open(routes_path, 'a', encoding='utf-8') as f:
        f.write(routes_addition)
    print(f"[OK] Added system update routes to {routes_path}")
else:
    print(f"[OK] {routes_path} already has system update routes")

print("\n[OK] System update routes added!")
