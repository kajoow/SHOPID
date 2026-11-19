from flask import Flask

def register_blueprints(app: Flask):
    from .auth import auth_bp
    from .products import products_bp
    from .cart import cart_bp
    from .orders import orders_bp
    from .user import user_bp
    from .wishlist import wishlist_bp
    from .notifications import notifications_bp
    from .reviews import reviews_bp
    from .admin import (
        admin_bp,
        admin_products_bp,
        admin_categories_bp,
        admin_orders_bp,
        admin_inventory_bp,
        admin_promotions_bp,
        admin_audit_bp,
        admin_users_bp,
        admin_reviews_bp,
    )

    app.register_blueprint(auth_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(wishlist_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(reviews_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(admin_products_bp)
    app.register_blueprint(admin_categories_bp)
    app.register_blueprint(admin_orders_bp)
    app.register_blueprint(admin_inventory_bp)
    app.register_blueprint(admin_promotions_bp)
    app.register_blueprint(admin_audit_bp)
    app.register_blueprint(admin_users_bp)
    app.register_blueprint(admin_reviews_bp)
