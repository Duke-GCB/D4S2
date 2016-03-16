from flask import Flask
app = Flask(__name__)

VERSION_PREFIX="/api/v1"

@app.route(VERSION_PREFIX + "/handovers")
def handovers():
  return "handovers\n"

@app.route(VERSION_PREFIX + "/drafts")
def drafts():
  return "drafts\n"

if __name__ == "__main__":
    app.run()
