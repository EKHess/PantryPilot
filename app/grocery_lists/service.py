from collections import OrderedDict
from app.db import get_db
from app.settings.repository import get_int

def needed_items(store_id=None):
    threshold=get_int("restock_threshold",1); params=[threshold]; store=""
    if store_id is not None: store=" AND s.id=?"; params.append(store_id)
    rows=get_db().execute("SELECT i.*,s.name store_name,s.display_order,COALESCE(i.restock_threshold,?) effective_threshold FROM inventory_items i JOIN stores s ON s.id=i.store_id WHERE i.is_active=1 AND s.is_active=1 AND i.quantity<=COALESCE(i.restock_threshold,?)"+store+" ORDER BY s.display_order,s.name,i.name", [threshold]+params).fetchall()
    groups=OrderedDict()
    for row in rows:
        item=dict(row); item["purchase_quantity"]=max((item["target_quantity"] or get_int("default_target_quantity",3))-item["quantity"],1); groups.setdefault(item["store_name"],[]).append(item)
    return groups

