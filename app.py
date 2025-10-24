from flask import Flask, flash, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
from sqlalchemy import func
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///grocery_pos.db'
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
db = SQLAlchemy(app)

# ==================== MODELS ====================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # superadmin, admin, sales
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    products = db.relationship('Product', backref='category', lazy=True, cascade='all, delete-orphan')

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    image_url = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    inventory_records = db.relationship('Inventory', backref='product', lazy=True, cascade='all, delete-orphan')

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    total_items = db.Column(db.Integer, nullable=False)
    sale_date = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('SaleItem', backref='sale', lazy=True, cascade='all, delete-orphan')

class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    product = db.relationship('Product')

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity_sold = db.Column(db.Integer, nullable=False)
    quantity_remaining = db.Column(db.Integer, nullable=False)
    record_date = db.Column(db.DateTime, default=datetime.utcnow)
    month = db.Column(db.String(20))
    year = db.Column(db.Integer)

# ==================== DECORATORS ====================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
    

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            user = User.query.get(session['user_id'])
            # allow superadmin to access any role-protected route
            if user.role != 'superadmin' and user.role not in roles:
                return redirect(url_for('unauthorized'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ==================== ROUTES ====================

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for("login"))
    user = User.query.get(session['user_id'])
    
    if user.role == 'superadmin':
        return redirect(url_for('superadmin_dashboard'))
    elif user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('home'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # form uses 'username' and 'password'
        username = request.form.get('username')
        password = request.form.get('password')

        # lookup user via SQLAlchemy
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            # store multiple session keys for templates and code compatibility
            session['user'] = user.username
            session['username'] = user.username
            session['user_id'] = user.id
            session['role'] = user.role
            flash("Login successful!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password", "danger")
            return redirect(url_for('login'))

    # GET -> render the login page
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/unauthorized')
def unauthorized():
    return render_template('unauthorized.html'), 403

# ==================== SUPERADMIN ROUTES ====================

@app.route('/superadmin/dashboard')
@role_required('superadmin')
def superadmin_dashboard():
    admins = User.query.filter_by(role='admin').all()
    sales_users = User.query.filter_by(role='sales').all()
    return render_template('superadmin_dashboard.html', admins=admins, sales_users=sales_users)

@app.route('/superadmin/add-user', methods=['GET', 'POST'])
@role_required('superadmin')
def add_user():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        
        if User.query.filter_by(username=username).first():
            return render_template('add_user.html', error='Username already exists')
        
        user = User(username=username, password=generate_password_hash(password), role=role)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('superadmin_dashboard'))
    
    return render_template('add_user.html')

@app.route('/superadmin/delete-user/<int:user_id>', methods=['POST'])
@role_required('superadmin')
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('superadmin_dashboard'))

# ==================== ADMIN ROUTES ====================

@app.route('/admin/dashboard')
@role_required('admin')
def admin_dashboard():
    categories = Category.query.all()
    products = Product.query.all()
    return render_template('admin_dashboard.html', categories=categories, products=products)

@app.route('/admin/categories', methods=['GET', 'POST'])
@role_required('admin')
def manage_categories():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        if Category.query.filter_by(name=name).first():
            categories = Category.query.all()
            return render_template('manage_categories.html', categories=categories, error='Category already exists')
        
        category = Category(name=name, description=description)
        db.session.add(category)
        db.session.commit()
        return redirect(url_for('manage_categories'))
    
    categories = Category.query.all()
    return render_template('manage_categories.html', categories=categories)

@app.route('/admin/categories/<int:cat_id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def edit_category(cat_id):
    category = Category.query.get_or_404(cat_id)
    if request.method == 'POST':
        category.name = request.form.get('name')
        category.description = request.form.get('description')
        db.session.commit()
        return redirect(url_for('manage_categories'))
    return render_template('edit_category.html', category=category)

@app.route('/admin/categories/<int:cat_id>/delete', methods=['POST'])
@role_required('admin')
def delete_category(cat_id):
    category = Category.query.get_or_404(cat_id)
    db.session.delete(category)
    db.session.commit()
    return redirect(url_for('manage_categories'))

@app.route('/admin/products', methods=['GET', 'POST'])
@role_required('admin')
def manage_products():
    if request.method == 'POST':
        name = request.form.get('name')
        category_id = request.form.get('category_id')
        price = request.form.get('price')
        stock = request.form.get('stock')
        image_url = request.form.get('image_url')
        
        product = Product(name=name, category_id=category_id, price=price, stock=stock, image_url=image_url)
        db.session.add(product)
        db.session.commit()
        return redirect(url_for('manage_products'))
    
    categories = Category.query.all()
    products = Product.query.all()
    return render_template('manage_products.html', categories=categories, products=products)

@app.route('/admin/products/<int:prod_id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def edit_product(prod_id):
    product = Product.query.get_or_404(prod_id)
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.category_id = request.form.get('category_id')
        product.price = request.form.get('price')
        product.stock = request.form.get('stock')
        product.image_url = request.form.get('image_url')
        db.session.commit()
        return redirect(url_for('manage_products'))
    
    categories = Category.query.all()
    return render_template('edit_product.html', product=product, categories=categories)

@app.route('/admin/products/<int:prod_id>/delete', methods=['POST'])
@role_required('admin')
def delete_product(prod_id):
    product = Product.query.get_or_404(prod_id)
    db.session.delete(product)
    db.session.commit()
    return redirect(url_for('manage_products'))

@app.route('/admin/inventory')
@role_required('admin')
def view_inventory():
    month_filter = request.args.get('month')
    year_filter = request.args.get('year')
    category_filter = request.args.get('category')
    # date filter in YYYY-MM-DD format for precise filtering
    date_filter = request.args.get('date')
    
    # list of months for the filter dropdown (ordered)
    months = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]

    # list of years available in inventory (ascending)
    years_query = db.session.query(Inventory.year).distinct().order_by(Inventory.year.asc()).all()
    years = [y[0] for y in years_query if y[0] is not None]

    query = Inventory.query
    if month_filter:
        query = query.filter_by(month=month_filter)
    if year_filter:
        try:
            y = int(year_filter)
            query = query.filter_by(year=y)
        except ValueError:
            pass
    if date_filter:
        # expect YYYY-MM-DD; use SQLite/SQLAlchemy date function to compare only the date part
        try:
            # validate format
            datetime.strptime(date_filter, '%Y-%m-%d')
            query = query.filter(func.date(Inventory.record_date) == date_filter)
        except ValueError:
            # ignore invalid date formats
            pass

    inventory = None
    # if a category is selected, show all products in that category
    # and compute quantity_sold for the selected month (or total if no month)
    if category_filter:
        try:
            cat_id = int(category_filter)
            products = Product.query.filter_by(category_id=cat_id).order_by(Product.name).all()

            inventory = []
            for p in products:
                inv_q = Inventory.query.filter_by(product_id=p.id)
                if month_filter:
                    inv_q = inv_q.filter_by(month=month_filter)
                if year_filter:
                    try:
                        inv_q = inv_q.filter_by(year=int(year_filter))
                    except ValueError:
                        pass
                if date_filter:
                    try:
                        # ensure format valid
                        datetime.strptime(date_filter, '%Y-%m-%d')
                        inv_q = inv_q.filter(func.date(Inventory.record_date) == date_filter)
                    except ValueError:
                        pass
                qty_sold = sum(i.quantity_sold for i in inv_q.all())
                inventory.append({
                    'product': p,
                    'quantity_sold': qty_sold,
                    'quantity_remaining': p.stock,
                    'month': month_filter,
                    'year': int(year_filter) if year_filter and year_filter.isdigit() else None,
                    'date': date_filter
                })
        except ValueError:
            # invalid category filter -> fall back to inventory query
            pass

    if inventory is None:
        if category_filter:
            try:
                cat_id = int(category_filter)
                query = query.join(Product).filter(Product.category_id == cat_id)
            except ValueError:
                pass
        inventory = query.all()
    # return categories sorted alphabetically (case-insensitive) so the select is ordered
    categories = Category.query.order_by(func.lower(Category.name)).all()
    return render_template('inventory.html', inventory=inventory, categories=categories, month_filter=month_filter, category_filter=category_filter, months=months, years=years, year_filter=year_filter, date_filter=date_filter)

# ==================== SALES ROUTES ====================

@app.route('/sales/home')
@role_required('sales')
def home():
    categories = Category.query.all()
    return render_template('sales_home.html', categories=categories)

@app.route('/api/products/<int:cat_id>')
@login_required
def get_products(cat_id):
    products = Product.query.filter_by(category_id=cat_id).all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'price': p.price,
        'stock': p.stock,
        'image_url': p.image_url
    } for p in products])

@app.route('/sales/checkout')
@role_required('sales')
def checkout():
    cart = session.get('cart', [])
    total_items = sum(item['quantity'] for item in cart)
    total_amount = sum(item['quantity'] * item['price'] for item in cart)
    # provide a current date/time string for display in the checkout page
    now = datetime.utcnow()
    date_for_checkout = now.strftime('%B %d, %Y %I:%M %p')
    return render_template('checkout.html', cart=cart, total_items=total_items, total_amount=total_amount, date_for_checkout=date_for_checkout)

@app.route('/api/add-to-cart', methods=['POST'])
@role_required('sales')
def add_to_cart():
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = int(data.get('quantity'))
    
    product = Product.query.get_or_404(product_id)
    
    if product.stock < quantity:
        return jsonify({'success': False, 'message': 'Insufficient stock'}), 400
    
    cart = session.get('cart', [])
    
    item_exists = False
    for item in cart:
        if item['id'] == product_id:
            item['quantity'] += quantity
            item_exists = True
            break
    
    if not item_exists:
        cart.append({
            'id': product_id,
            'name': product.name,
            'price': product.price,
            'quantity': quantity,
            'image_url': product.image_url
        })
    
    session['cart'] = cart
    session.modified = True
    return jsonify({'success': True, 'message': 'Item added to cart'})

@app.route('/api/remove-from-cart/<int:product_id>', methods=['POST'])
@role_required('sales')
def remove_from_cart(product_id):
    cart = session.get('cart', [])
    cart = [item for item in cart if item['id'] != product_id]
    session['cart'] = cart
    session.modified = True
    return jsonify({'success': True})

@app.route('/api/process-sale', methods=['POST'])
@role_required('sales')
def process_sale():
    cart = session.get('cart', [])
    if not cart:
        return jsonify({'success': False, 'message': 'Cart is empty'}), 400
    
    total_amount = sum(item['quantity'] * item['price'] for item in cart)
    total_items = sum(item['quantity'] for item in cart)
    
    sale = Sale(user_id=session['user_id'], total_amount=total_amount, total_items=total_items)
    db.session.add(sale)
    db.session.flush()
    
    for item in cart:
        product = Product.query.get(item['id'])
        product.stock -= item['quantity']
        
        sale_item = SaleItem(sale_id=sale.id, product_id=item['id'], quantity=item['quantity'], price=item['price'])
        db.session.add(sale_item)
        
        now = datetime.utcnow()
        inventory = Inventory(
            product_id=item['id'],
            quantity_sold=item['quantity'],
            quantity_remaining=product.stock,
            month=now.strftime('%B'),
            year=now.year
        )
        db.session.add(inventory)
    
    db.session.commit()
    session['cart'] = []
    session.modified = True
    
    return jsonify({'success': True, 'sale_id': sale.id})

@app.route('/sales/receipt/<int:sale_id>')
@role_required('sales')
def receipt(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    return render_template('receipt.html', sale=sale)

@app.route('/sales/history')
@role_required('sales')
def sales_history():
    sales = Sale.query.filter_by(user_id=session['user_id']).all()
    return render_template('sales_history.html', sales=sales)

# ==================== DATABASE INITIALIZATION ====================

def init_db():
    with app.app_context():
        db.create_all()
        
        if User.query.count() == 0:
            superadmin = User(username='superadmin', password=generate_password_hash('superadmin123'), role='superadmin')
            db.session.add(superadmin)
            db.session.commit()
            print("Superadmin created: superadmin / superadmin123")

if __name__ == '__main__':
    init_db()
    app.run(debug=True)