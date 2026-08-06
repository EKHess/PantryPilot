from app.db import get_db
def test_pages_render(client):
    for path in ('/','/inventory','/grocery-lists','/stores','/settings','/grocery-lists/print'): assert client.get(path).status_code==200
def test_needed_boundary_and_grouping(client):
    data=client.get('/api/grocery-lists/needed').get_json()['stores']; assert [s['name'] for s in data]==['Costco','Fresh Market']; assert [i['name'] for s in data for i in s['items']]==['Milk','Bananas']
def test_create_duplicate_and_validation(client):
    assert client.post('/api/inventory',json={'name':'Eggs','quantity':2,'store_id':1}).status_code==201
    assert client.post('/api/inventory',json={'name':'Eggs','quantity':2,'store_id':1}).status_code==409
    assert client.post('/api/inventory',json={'name':'','quantity':-1}).status_code==400
def test_quantity_adjustment_is_atomic(app,client):
    response=client.patch('/api/inventory/1/quantity',json={'operation':'increment','amount':2}); assert response.get_json()['item']['quantity']==2
    assert client.patch('/api/inventory/1/quantity',json={'quantity':-1}).status_code==400
    with app.app_context(): assert get_db().execute('SELECT COUNT(*) FROM inventory_adjustments').fetchone()[0]==1
def test_search_suggestions_and_sort_guard(client):
    assert client.get('/api/inventory/suggestions?q=m').get_json()=={'suggestions':[]}
    assert client.get('/api/inventory/suggestions?q=mi').get_json()['suggestions'][0]['name']=='Milk'
    assert client.get('/api/inventory?sort=name;DROP TABLE stores').status_code==200
def test_pdf_downloads(client):
    response=client.get('/grocery-lists/download.pdf'); assert response.status_code==200; assert response.data.startswith(b'%PDF'); assert 'grocery-list-' in response.headers['Content-Disposition']
    response=client.get('/grocery-lists/stores/1/download.pdf'); assert response.status_code==200; assert 'costco' in response.headers['Content-Disposition']
def test_settings_change_threshold(client):
    assert client.patch('/api/settings',json={'restock_threshold':3}).status_code==200
    names=[i['name'] for s in client.get('/api/grocery-lists/needed').get_json()['stores'] for i in s['items']]; assert 'Rice' in names
def test_store_delete_conflict(client): assert client.delete('/api/stores/1').status_code==409

