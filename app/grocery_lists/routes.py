from datetime import datetime,timezone
from io import BytesIO
import re
from flask import Blueprint,abort,jsonify,render_template,send_file
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas
from .service import needed_items
from app.settings.repository import get_int
from app.db import get_db
bp=Blueprint("grocery_lists",__name__)

@bp.get("/grocery-lists")
def page():
    groups=needed_items(); return render_template("grocery_lists/index.html",groups=groups,count=sum(map(len,groups.values())),threshold=get_int("restock_threshold",1))
@bp.get("/api/grocery-lists/needed")
def api_needed(): return jsonify(stores=[{"name":name,"items":items} for name,items in needed_items().items()])
@bp.get("/grocery-lists/print")
def print_view(): return render_template("grocery_lists/print.html",groups=needed_items(),generated=datetime.now(timezone.utc),threshold=get_int("restock_threshold",1))

def pdf_response(groups,filename):
    stream=BytesIO(); pdf=Canvas(stream,pagesize=letter); width,height=letter; y=height-54
    pdf.setTitle("PantryPilot Grocery List"); pdf.setFont("Helvetica-Bold",18); pdf.drawString(54,y,"PantryPilot Grocery List"); y-=22; pdf.setFont("Helvetica",9); pdf.drawString(54,y,"Generated "+datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")); y-=28
    if not groups: pdf.drawString(54,y,"You're all stocked up — no items are needed.")
    for store,items in groups.items():
        if y<100: pdf.showPage(); y=height-54
        pdf.setFont("Helvetica-Bold",13); pdf.drawString(54,y,store.upper()); y-=20
        for item in items:
            pdf.rect(56,y-2,9,9); pdf.setFont("Helvetica",10); pdf.drawString(74,y,item["name"]); pdf.drawRightString(width-54,y,f"Have: {item['quantity']}   Buy: {item['purchase_quantity']}"); y-=18
        y-=10
    pdf.save(); stream.seek(0); return send_file(stream,mimetype="application/pdf",as_attachment=True,download_name=filename)
@bp.get("/grocery-lists/download.pdf")
def combined_pdf(): return pdf_response(needed_items(),datetime.now(timezone.utc).strftime("grocery-list-%Y-%m-%d.pdf"))
@bp.get("/grocery-lists/stores/<int:store_id>/download.pdf")
def store_pdf(store_id):
    store=get_db().execute("SELECT name FROM stores WHERE id=?",(store_id,)).fetchone()
    if not store: abort(404)
    slug=re.sub(r"[^a-z0-9]+","-",store["name"].lower()).strip("-") or "store"
    return pdf_response(needed_items(store_id),datetime.now(timezone.utc).strftime(f"grocery-list-{slug}-%Y-%m-%d.pdf"))
