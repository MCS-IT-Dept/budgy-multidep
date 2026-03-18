class TestRoleAccess:
    def _login(self, client, user):
        """Helper to log in a user in the test client."""
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)

    def test_user_cannot_access_admin(self, client, staff_user):
        self._login(client, staff_user)
        resp = client.get("/admin/", follow_redirects=False)
        assert resp.status_code == 403

    def test_global_admin_can_access_admin(self, client, admin_user):
        self._login(client, admin_user)
        resp = client.get("/admin/")
        assert resp.status_code == 200

    def test_user_cannot_access_global_dashboard(self, client, staff_user):
        self._login(client, staff_user)
        resp = client.get("/dashboard/", follow_redirects=False)
        assert resp.status_code == 403

    def test_unauthenticated_redirects_to_login(self, client, default_department):
        resp = client.get(f"/dept/{default_department.id}/", follow_redirects=False)
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]

    def test_dept_admin_can_access_dept_dashboard(self, client, dept_admin_user, default_department):
        self._login(client, dept_admin_user)
        resp = client.get(f"/dashboard/dept/{default_department.id}")
        assert resp.status_code == 200
