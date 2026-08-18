import sys

# Fix test_admin_catalog.py
with open('tests/test_admin_catalog.py', 'r') as f:
    content = f.read()

content = content.replace('response.json()["error"]["details"]', 'response.json()["error"]["message"]')

with open('tests/test_admin_catalog.py', 'w') as f:
    f.write(content)

# Fix test_storage.py
with open('tests/test_storage.py', 'r') as f:
    content = f.read()

content = content.replace('response = client.post(', 'response = client.post(')
# wait, better way:
new_code = '''@patch("starlette.datastructures.UploadFile.close")
def test_unexpected_exception_cleanup(mock_close, mock_admin_auth, mock_crud_product_admin, mock_storage):
    prod_id = uuid.uuid4()
    mock_crud_product_admin.get_product_by_id.side_effect = Exception("Unexpected error")
    
    custom_client = TestClient(app, raise_server_exceptions=False)
    response = custom_client.post(
        f"/api/v1/admin/products/{prod_id}/image",
        headers={"Authorization": "Bearer token"},
        files={"file": ("test.png", io.BytesIO(b"fake"), "image/png")}
    )
    assert response.status_code == 500
    assert mock_close.call_count >= 1'''

old_code = '''@patch("starlette.datastructures.UploadFile.close")
def test_unexpected_exception_cleanup(mock_close, mock_admin_auth, mock_crud_product_admin, mock_storage):
    prod_id = uuid.uuid4()
    mock_crud_product_admin.get_product_by_id.side_effect = Exception("Unexpected error")
    
    response = client.post(
        f"/api/v1/admin/products/{prod_id}/image",
        headers={"Authorization": "Bearer token"},
        files={"file": ("test.png", io.BytesIO(b"fake"), "image/png")}
    )
    assert response.status_code == 500
    assert mock_close.call_count >= 1'''

content = content.replace(old_code, new_code)

with open('tests/test_storage.py', 'w') as f:
    f.write(content)

