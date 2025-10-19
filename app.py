from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///pos_database.db"
app.config["SECRET_KEY"] = "your-secret-key-here"
db = SQLAlchemy(app)


# Models
class Product(db.Model):
    """Product Model for Inventory"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Product {self.name}>'


class Sale(db.Model):
    """Sale Model for Transaction Records"""
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    date_sold = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Sale {self.id}>'


# Routes
@app.route('/')
def home():
    """Homepage - Grocery Store"""
    return render_template('home.html')


@app.route('/inventory')
def inventory():
    """View all inventory items"""
    products = Product.query.order_by(Product.category, Product.name).all()

    # Group products by category
    categories = {}
    for product in products:
        if product.category not in categories:
            categories[product.category] = []
        categories[product.category].append(product)

    return render_template('inventory.html', categories=categories)


@app.route('/add', methods=['GET', 'POST'])
def add_product():
    """Add new product to inventory"""
    if request.method == 'POST':
        name = request.form['name']
        category = request.form['category']
        price = float(request.form['price'])
        stock = int(request.form['stock'])

        new_product = Product(name=name, category=category, price=price, stock=stock)

        try:
            db.session.add(new_product)
            db.session.commit()
            flash('Product added successfully!', 'success')
            return redirect(url_for('inventory'))
        except Exception as e:
            flash(f'Error adding product: {e}', 'error')
            return redirect(url_for('add_product'))

    return render_template('add_product.html')


@app.route('/update/<int:id>', methods=['GET', 'POST'])
def update_product(id):
    """Update existing product"""
    product = Product.query.get_or_404(id)

    if request.method == 'POST':
        product.name = request.form['name']
        product.category = request.form['category']
        product.price = float(request.form['price'])
        product.stock = int(request.form['stock'])

        try:
            db.session.commit()
            flash('Product updated successfully!', 'success')
            return redirect(url_for('inventory'))
        except Exception as e:
            flash(f'Error updating product: {e}', 'error')
            return redirect(url_for('update_product', id=id))

    return render_template('update_product.html', product=product)


@app.route('/delete/<int:id>')
def delete_product(id):
    """Delete product from inventory"""
    product = Product.query.get_or_404(id)

    try:
        db.session.delete(product)
        db.session.commit()
        flash('Product deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting product: {e}', 'error')

    return redirect(url_for('inventory'))


@app.route('/sales', methods=['GET', 'POST'])
def sales():
    """Process sales transactions"""
    if request.method == 'POST':
        product_id = int(request.form['product_id'])
        quantity = int(request.form['quantity'])

        product = Product.query.get_or_404(product_id)

        if product.stock < quantity:
            flash('Insufficient stock!', 'error')
            return redirect(url_for('sales'))

        total_price = product.price * quantity

        new_sale = Sale(
            product_id=product.id,
            product_name=product.name,
            quantity=quantity,
            unit_price=product.price,
            total_price=total_price
        )

        product.stock -= quantity

        try:
            db.session.add(new_sale)
            db.session.commit()
            flash(f'Sale completed! Total: ₱{total_price:.2f}', 'success')
            return redirect(url_for('sales'))
        except Exception as e:
            flash(f'Error processing sale: {e}', 'error')
            return redirect(url_for('sales'))

    products = Product.query.filter(Product.stock > 0).all()
    recent_sales = Sale.query.order_by(Sale.date_sold.desc()).limit(10).all()
    return render_template('sales.html', products=products, recent_sales=recent_sales)


@app.route('/sales/history')
def sales_history():
    """View all sales history"""
    sales = Sale.query.order_by(Sale.date_sold.desc()).all()
    total_revenue = sum(sale.total_price for sale in sales)
    return render_template('sales_history.html', sales=sales, total_revenue=total_revenue)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)