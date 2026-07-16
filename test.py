import httpx

requests =httpx.Client()

for i in range(-200, 100000):
    inp = requests.post("http://192.9.183.81:8101/index.php", data={"level5_choice": "{i}"})
    print(inp.content)
