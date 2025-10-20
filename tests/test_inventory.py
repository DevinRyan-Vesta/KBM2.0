from utilities.database import db, Property, Contact, SmartLock


def test_healthcheck(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json == {"ok": True}


def test_lockbox_list(auth_client, sample_lockbox):
    response = auth_client.get("/inventory/lockboxes")
    assert response.status_code == 200
    assert sample_lockbox.label.encode() in response.data


def test_item_details_page(auth_client, sample_lockbox):
    response = auth_client.get(f"/inventory/items/{sample_lockbox.id}")
    assert response.status_code == 200
    assert sample_lockbox.label.encode() in response.data


def test_checkout_api_lookup(auth_client, sample_lockbox):
    response = auth_client.get(f"/checkout/api/items/{sample_lockbox.custom_id}")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["id"] == sample_lockbox.id
    assert payload["custom_id"] == sample_lockbox.custom_id


def test_create_property_flow(auth_client, app):
    response = auth_client.post(
        "/properties/new",
        data={
            "name": "Test Property",
            "type": "single_family",
            "address_line1": "123 Main St",
            "city": "Springfield",
            "state": "IL",
            "postal_code": "62701",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        prop = Property.query.filter_by(name="Test Property").first()
        assert prop is not None
        prop_id = prop.id
    search_response = auth_client.get("/properties/api/search?q=Test")
    assert search_response.status_code == 200
    results = search_response.get_json()
    assert any(entry["id"] == prop_id for entry in results)


def test_create_contact_flow(auth_client, app):
    response = auth_client.post(
        "/contacts/new",
        data={
            "name": "Jordan Contractor",
            "contact_type": "contractor",
            "company": "Jordan Builders",
            "email": "jordan@example.com",
            "phone": "555-0101",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        contact = Contact.query.filter_by(email="jordan@example.com").first()
        assert contact is not None
        contact_id = contact.id
    detail_response = auth_client.get(f"/contacts/{contact_id}")
    assert detail_response.status_code == 200


def test_create_smartlock(auth_client, app):
    with app.app_context():
        property_obj = Property(
            name="Smart Lock Property",
            type="single_family",
            address_line1="456 Elm St",
        )
        db.session.add(property_obj)
        db.session.commit()
        property_id = property_obj.id
    response = auth_client.post(
        "/smart-locks/new",
        data={
            "label": "Front Door",
            "code": "1234",
            "provider": "August",
            "property_id": str(property_id),
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        lock = SmartLock.query.filter_by(label="Front Door").first()
        assert lock is not None
        assert lock.property_id == property_id
