import sys
code = '''
@patch('starlette.datastructures.UploadFile.close')
def test_database_update_failure_cleanup(mock_close, mock_admin_auth, mock_crud_product_admin, mock_storage):
    prod_id = uuid.uuid4()
    p = Product(id=prod_id, category_id=uuid.uuid4(), is_active=True, image_url=None)
    mock_crud_product_admin.get_product_by_id.return_value = p
    mock_storage.upload_product_image.return_value = "https://example.com/new.png"
    
    mock_admin_auth.commit.side_effect = Exception("DB Down")
    
    response = client.post(
        f"/api/v1/admin/products/{prod_id}/image",
        headers={"Authorization": "Bearer token"},
        files={"file": ("test.png", io.BytesIO(b"fake"), "image/png")}
    )
    assert response.status_code == 500
    assert mock_close.call_count >= 1

@patch('starlette.datastructures.UploadFile.close')
def test_unexpected_exception_cleanup(mock_close, mock_admin_auth, mock_crud_product_admin, mock_storage):
    prod_id = uuid.uuid4()
    mock_crud_product_admin.get_product_by_id.side_effect = Exception("Unexpected error")
    
    response = client.post(
        f"/api/v1/admin/products/{prod_id}/image",
        headers={"Authorization": "Bearer token"},
        files={"file": ("test.png", io.BytesIO(b"fake"), "image/png")}
    )
    assert response.status_code == 500
    assert mock_close.call_count >= 1

def test_unauthorized_image_upload():
    prod_id = uuid.uuid4()
    response = client.post(
        f"/api/v1/admin/products/{prod_id}/image",
        files={"file": ("test.png", io.BytesIO(b"fake"), "image/png")}
    )
    assert response.status_code == 401

def test_unauthorized_image_deletion():
    prod_id = uuid.uuid4()
    response = client.delete(
        f"/api/v1/admin/products/{prod_id}/image"
    )
    assert response.status_code == 401
'''
with open('tests/test_storage.py', 'a') as f:
    f.write(code)
