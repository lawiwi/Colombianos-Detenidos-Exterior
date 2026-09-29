from flask import Flask, render_template

app = Flask(__name__)

# --- RUTAS ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dimension-1')
def dimension_1():
    return render_template('dim_1.html', titulo="Dimensión 1")

@app.route('/dimension-2')
def dimension_2():
    return render_template('dim_2.html', titulo="Dimensión 2")

@app.route('/dimension-3')
def dimension_3():
    return render_template('dim_3.html', titulo="Dimensión 3")

@app.route('/dimension-4')
def dimension_4():
    return render_template('dim_4.html', titulo="Dimensión 4")

if __name__ == '__main__':
    app.run(debug=True)
