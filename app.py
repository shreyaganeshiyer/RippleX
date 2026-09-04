from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="RippleX")


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>RippleX</title>
    </head>
    <body>
        <h1>RippleX</h1>
        <p>AI Supply Chain Disruption Command Center</p>
    </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)