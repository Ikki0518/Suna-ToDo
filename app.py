from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello():
    return 'Hello from Vercel + Flask!'

@app.route('/test')
def test():
    return 'Test page is working!'

# Vercel用
if __name__ == '__main__':
    app.run(debug=True)