"""Tests for Notification CRUD, read/unread, unread count, delete, and user filtering."""
import pytest
from uuid import uuid4

from app.models.notification import Notification


class TestNotificationCRUD:
    def test_list_notifications(self, client, ceo_headers, sample_notification):
        response = client.get("/api/v1/notifications/", headers=ceo_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_notification_via_service(self, db, neon_user):
        from app.services.notification_service import NotificationService
        from app.schemas.notification import NotificationCreate

        service = NotificationService(db)
        data = NotificationCreate(
            user_id=neon_user.id,
            type="alert",
            title="Service Test Notification",
            message="Created via service layer",
            priority="medium",
        )
        notification = service.create_notification(data)
        assert notification.title == "Service Test Notification"
        assert notification.user_id == neon_user.id
        assert notification.is_read is False

    def test_list_notifications_empty(self, client, ceo_headers):
        response = client.get("/api/v1/notifications/", headers=ceo_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_notifications_has_expected_fields(self, client, user_headers, sample_notification):
        response = client.get("/api/v1/notifications/", headers=user_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        notif = data[0]
        assert "id" in notif
        assert "user_id" in notif
        assert "type" in notif
        assert "title" in notif
        assert "message" in notif
        assert "is_read" in notif
        assert "priority" in notif
        assert "created_at" in notif

    def test_create_notification_direct(self, db, neon_user):
        notification = Notification(
            id=uuid4(),
            user_id=neon_user.id,
            type="warning",
            title="Direct Create",
            message="Created directly",
            is_read=False,
            priority="high",
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        assert notification.id is not None
        assert notification.title == "Direct Create"

    def test_unauthorized_list_notifications(self, client):
        response = client.get("/api/v1/notifications/")
        assert response.status_code == 401


class TestNotificationRead:
    def test_mark_as_read(self, client, user_headers, sample_notification):
        response = client.post(
            f"/api/v1/notifications/{sample_notification.id}/read",
            headers=user_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_read"] is True

    def test_mark_as_read_not_found(self, client, user_headers):
        fake_id = uuid4()
        response = client.post(
            f"/api/v1/notifications/{fake_id}/read",
            headers=user_headers,
        )
        assert response.status_code == 404

    def test_mark_as_read_already_read(self, client, user_headers, sample_notification):
        client.post(
            f"/api/v1/notifications/{sample_notification.id}/read",
            headers=user_headers,
        )
        response = client.post(
            f"/api/v1/notifications/{sample_notification.id}/read",
            headers=user_headers,
        )
        assert response.status_code == 200
        assert response.json()["is_read"] is True

    def test_mark_all_as_read(self, client, user_headers, sample_notification):
        response = client.post(
            "/api/v1/notifications/read-all",
            headers=user_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "marked" in data
        assert data["marked"] >= 1

    def test_mark_all_as_read_only_unread(self, client, user_headers, sample_notification):
        client.post(
            f"/api/v1/notifications/{sample_notification.id}/read",
            headers=user_headers,
        )
        response = client.post(
            "/api/v1/notifications/read-all",
            headers=user_headers,
        )
        assert response.status_code == 200
        assert response.json()["marked"] == 0

    def test_mark_all_as_read_multiple_unread(self, db, user_token, regular_user, api_db):
        for i in range(3):
            notif = Notification(
                id=uuid4(),
                user_id=regular_user.id,
                type="info",
                title=f"Bulk Read Test {i}",
                message=f"Message {i}",
                is_read=False,
                priority="low",
            )
            api_db.add(notif)
        api_db.commit()

        from fastapi.testclient import TestClient
        from app.main import app
        from app.database.session import get_db

        def override_get_db():
            yield api_db

        app.dependency_overrides[get_db] = override_get_db
        headers = {"Authorization": f"Bearer {user_token}"}
        with TestClient(app) as c:
            response = c.post("/api/v1/notifications/read-all", headers=headers)
        app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["marked"] == 3

    def test_unauthorized_mark_read(self, client):
        fake_id = uuid4()
        response = client.post(f"/api/v1/notifications/{fake_id}/read")
        assert response.status_code == 401


class TestNotificationUnreadCount:
    def test_unread_count_zero(self, client, ceo_headers):
        response = client.get(
            "/api/v1/notifications/unread-count",
            headers=ceo_headers,
        )
        assert response.status_code == 200
        assert response.json()["count"] == 0

    def test_unread_count_with_unread(self, client, user_headers, sample_notification):
        response = client.get(
            "/api/v1/notifications/unread-count",
            headers=user_headers,
        )
        assert response.status_code == 200
        assert response.json()["count"] >= 1

    def test_unread_count_after_mark_read(self, client, user_headers, sample_notification):
        count_before = client.get(
            "/api/v1/notifications/unread-count",
            headers=user_headers,
        ).json()["count"]

        client.post(
            f"/api/v1/notifications/{sample_notification.id}/read",
            headers=user_headers,
        )

        count_after = client.get(
            "/api/v1/notifications/unread-count",
            headers=user_headers,
        ).json()["count"]
        assert count_after == count_before - 1

    def test_unread_count_after_mark_all_read(self, client, user_headers, sample_notification):
        client.post(
            "/api/v1/notifications/read-all",
            headers=user_headers,
        )
        response = client.get(
            "/api/v1/notifications/unread-count",
            headers=user_headers,
        )
        assert response.status_code == 200
        assert response.json()["count"] == 0

    def test_unread_count_multiple_unread(self, db, regular_user, api_db):
        for i in range(5):
            notif = Notification(
                id=uuid4(),
                user_id=regular_user.id,
                type="info",
                title=f"Count Test {i}",
                message=f"Message {i}",
                is_read=False,
                priority="low",
            )
            api_db.add(notif)
        api_db.commit()

        from fastapi.testclient import TestClient
        from app.main import app
        from app.database.session import get_db
        from app.utils.security import create_access_token

        def override_get_db():
            yield api_db

        app.dependency_overrides[get_db] = override_get_db
        token = create_access_token(data={"sub": str(regular_user.id)})
        headers = {"Authorization": f"Bearer {token}"}
        with TestClient(app) as c:
            response = c.get("/api/v1/notifications/unread-count", headers=headers)
        app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["count"] == 5

    def test_unauthorized_unread_count(self, client):
        response = client.get("/api/v1/notifications/unread-count")
        assert response.status_code == 401


class TestNotificationDelete:
    def test_delete_notification(self, client, user_headers, sample_notification):
        response = client.delete(
            f"/api/v1/notifications/{sample_notification.id}",
            headers=user_headers,
        )
        assert response.status_code == 200
        assert response.json()["detail"] == "Notification deleted"

        get_response = client.get(
            "/api/v1/notifications/",
            headers=user_headers,
        )
        notif_ids = [n["id"] for n in get_response.json()]
        assert str(sample_notification.id) not in notif_ids

    def test_delete_notification_not_found(self, client, user_headers):
        fake_id = uuid4()
        response = client.delete(
            f"/api/v1/notifications/{fake_id}",
            headers=user_headers,
        )
        assert response.status_code == 404

    def test_delete_notification_via_service(self, db, neon_notification):
        from app.services.notification_service import NotificationService

        service = NotificationService(db)
        result = service.delete_notification(neon_notification.id)
        assert result is True
        assert service.get_notification(neon_notification.id) is None

    def test_delete_nonexistent_via_service(self, db):
        from app.services.notification_service import NotificationService

        service = NotificationService(db)
        result = service.delete_notification(uuid4())
        assert result is False

    def test_delete_does_not_affect_others(self, db, regular_user, api_db):
        notif1 = Notification(
            id=uuid4(),
            user_id=regular_user.id,
            type="info",
            title="Keep Me",
            message="Stay",
            is_read=False,
            priority="low",
        )
        notif2 = Notification(
            id=uuid4(),
            user_id=regular_user.id,
            type="info",
            title="Delete Me",
            message="Gone",
            is_read=False,
            priority="low",
        )
        api_db.add(notif1)
        api_db.add(notif2)
        api_db.commit()

        from fastapi.testclient import TestClient
        from app.main import app
        from app.database.session import get_db
        from app.utils.security import create_access_token

        def override_get_db():
            yield api_db

        app.dependency_overrides[get_db] = override_get_db
        token = create_access_token(data={"sub": str(regular_user.id)})
        headers = {"Authorization": f"Bearer {token}"}
        with TestClient(app) as c:
            response = c.delete(f"/api/v1/notifications/{notif2.id}", headers=headers)
        app.dependency_overrides.clear()

        assert response.status_code == 200

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as c:
            list_response = c.get("/api/v1/notifications/", headers=headers)
        app.dependency_overrides.clear()

        remaining_ids = [n["id"] for n in list_response.json()]
        assert str(notif1.id) in remaining_ids
        assert str(notif2.id) not in remaining_ids

    def test_unauthorized_delete(self, client):
        fake_id = uuid4()
        response = client.delete(f"/api/v1/notifications/{fake_id}")
        assert response.status_code == 401


class TestNotificationUserFilter:
    def test_users_only_see_own_notifications(self, db, regular_user, api_db):
        from app.models.user import User
        from app.utils.security import create_access_token

        other_user = User(
            id=uuid4(),
            email="other@test.com",
            name="Other User",
            role="user",
            is_active=True,
        )
        api_db.add(other_user)
        api_db.commit()

        my_notif = Notification(
            id=uuid4(),
            user_id=regular_user.id,
            type="info",
            title="My Notification",
            message="Mine",
            is_read=False,
            priority="low",
        )
        other_notif = Notification(
            id=uuid4(),
            user_id=other_user.id,
            type="info",
            title="Their Notification",
            message="Theirs",
            is_read=False,
            priority="low",
        )
        api_db.add(my_notif)
        api_db.add(other_notif)
        api_db.commit()

        from fastapi.testclient import TestClient
        from app.main import app
        from app.database.session import get_db

        def override_get_db():
            yield api_db

        app.dependency_overrides[get_db] = override_get_db
        my_token = create_access_token(data={"sub": str(regular_user.id)})
        my_headers = {"Authorization": f"Bearer {my_token}"}
        with TestClient(app) as c:
            my_response = c.get("/api/v1/notifications/", headers=my_headers)
        app.dependency_overrides.clear()

        assert my_response.status_code == 200
        my_ids = [n["id"] for n in my_response.json()]
        assert str(my_notif.id) in my_ids
        assert str(other_notif.id) not in my_ids

    def test_other_user_sees_only_own(self, db, regular_user, api_db):
        from app.models.user import User
        from app.utils.security import create_access_token

        other_user = User(
            id=uuid4(),
            email="second@test.com",
            name="Second User",
            role="user",
            is_active=True,
        )
        api_db.add(other_user)
        api_db.commit()

        my_notif = Notification(
            id=uuid4(),
            user_id=regular_user.id,
            type="info",
            title="First User Notif",
            message="First",
            is_read=False,
            priority="low",
        )
        other_notif = Notification(
            id=uuid4(),
            user_id=other_user.id,
            type="info",
            title="Second User Notif",
            message="Second",
            is_read=False,
            priority="low",
        )
        api_db.add(my_notif)
        api_db.add(other_notif)
        api_db.commit()

        from fastapi.testclient import TestClient
        from app.main import app
        from app.database.session import get_db

        def override_get_db():
            yield api_db

        app.dependency_overrides[get_db] = override_get_db
        other_token = create_access_token(data={"sub": str(other_user.id)})
        other_headers = {"Authorization": f"Bearer {other_token}"}
        with TestClient(app) as c:
            other_response = c.get("/api/v1/notifications/", headers=other_headers)
        app.dependency_overrides.clear()

        assert other_response.status_code == 200
        other_ids = [n["id"] for n in other_response.json()]
        assert str(other_notif.id) in other_ids
        assert str(my_notif.id) not in other_ids

    def test_unread_count_per_user(self, db, regular_user, api_db):
        from app.models.user import User
        from app.utils.security import create_access_token

        other_user = User(
            id=uuid4(),
            email="count_user@test.com",
            name="Count User",
            role="user",
            is_active=True,
        )
        api_db.add(other_user)
        api_db.commit()

        for i in range(3):
            api_db.add(Notification(
                id=uuid4(),
                user_id=regular_user.id,
                type="info",
                title=f"My Unread {i}",
                message="x",
                is_read=False,
                priority="low",
            ))
        api_db.add(Notification(
            id=uuid4(),
            user_id=other_user.id,
            type="info",
            title="Other Unread",
            message="y",
            is_read=False,
            priority="low",
        ))
        api_db.commit()

        from fastapi.testclient import TestClient
        from app.main import app
        from app.database.session import get_db

        def override_get_db():
            yield api_db

        app.dependency_overrides[get_db] = override_get_db
        my_token = create_access_token(data={"sub": str(regular_user.id)})
        my_headers = {"Authorization": f"Bearer {my_token}"}
        with TestClient(app) as c:
            my_count = c.get("/api/v1/notifications/unread-count", headers=my_headers)
        app.dependency_overrides.clear()

        assert my_count.status_code == 200
        assert my_count.json()["count"] == 3

    def test_mark_read_does_not_affect_other_user(self, db, regular_user, api_db):
        from app.models.user import User
        from app.utils.security import create_access_token

        other_user = User(
            id=uuid4(),
            email="isolation@test.com",
            name="Isolation User",
            role="user",
            is_active=True,
        )
        api_db.add(other_user)
        api_db.commit()

        my_notif = Notification(
            id=uuid4(),
            user_id=regular_user.id,
            type="info",
            title="My Read Test",
            message="x",
            is_read=False,
            priority="low",
        )
        other_notif = Notification(
            id=uuid4(),
            user_id=other_user.id,
            type="info",
            title="Other Read Test",
            message="y",
            is_read=False,
            priority="low",
        )
        api_db.add(my_notif)
        api_db.add(other_notif)
        api_db.commit()

        from fastapi.testclient import TestClient
        from app.main import app
        from app.database.session import get_db

        def override_get_db():
            yield api_db

        app.dependency_overrides[get_db] = override_get_db
        my_token = create_access_token(data={"sub": str(regular_user.id)})
        my_headers = {"Authorization": f"Bearer {my_token}"}
        with TestClient(app) as c:
            c.post(f"/api/v1/notifications/{my_notif.id}/read", headers=my_headers)
        app.dependency_overrides.clear()

        app.dependency_overrides[get_db] = override_get_db
        other_token = create_access_token(data={"sub": str(other_user.id)})
        other_headers = {"Authorization": f"Bearer {other_token}"}
        with TestClient(app) as c:
            other_count = c.get("/api/v1/notifications/unread-count", headers=other_headers)
        app.dependency_overrides.clear()

        assert other_count.status_code == 200
        assert other_count.json()["count"] == 1

    def test_notification_service_user_filter(self, db, regular_user, api_db):
        from app.services.notification_service import NotificationService
        from app.models.user import User

        other_user = User(
            id=uuid4(),
            email="svc_filter@test.com",
            name="Service Filter User",
            role="user",
            is_active=True,
        )
        api_db.add(other_user)
        api_db.commit()

        my_notif = Notification(
            id=uuid4(),
            user_id=regular_user.id,
            type="info",
            title="Service Filter Mine",
            message="x",
            is_read=False,
            priority="low",
        )
        other_notif = Notification(
            id=uuid4(),
            user_id=other_user.id,
            type="info",
            title="Service Filter Other",
            message="y",
            is_read=False,
            priority="low",
        )
        api_db.add(my_notif)
        api_db.add(other_notif)
        api_db.commit()

        service = NotificationService(db)
        my_notifs = service.get_notifications(regular_user.id)
        other_notifs = service.get_notifications(other_user.id)

        my_ids = [n.id for n in my_notifs]
        other_ids = [n.id for n in other_notifs]

        assert my_notif.id in my_ids
        assert other_notif.id not in my_ids
        assert other_notif.id in other_ids
        assert my_notif.id not in other_ids
