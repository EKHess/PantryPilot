import os,tempfile,pytest
from app import create_app
from app.db import get_db,init_db
@pytest.fixture()
def app():
    fd,path=tempfile.mkstemp(); app=create_app({"TESTING":True,"DATABASE":path,"SECRET_KEY":"test"})
    with app.app_context():
        init_db(); db=get_db(); db.execute("INSERT INTO stores(name) VALUES('Costco'),('Fresh Market')"); db.execute("INSERT INTO inventory_items(name,quantity,store_id,target_quantity) VALUES('Milk',0,1,2),('Rice',3,1,5),('Bananas',1,2,6)"); db.commit()
    yield app; os.close(fd); os.unlink(path)
@pytest.fixture()
def client(app): return app.test_client()

