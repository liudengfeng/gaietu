# 实用脚本

## JSON -> TOML

JSON and TOML are two different file formats, but the core idea is pretty similar - they both make it easy to pass around a bunch of string keys and their corresponding values. (One way to think of JSON & TOML are as representations of a Python dictionary, but written as a file.) Firestore gave us our secrets as a JSON file, but Streamlit secrets expect a TOML; let's convert between them with a Python script!

```python
import toml

# output_file = ".streamlit/secrets.toml"
output_file = ".streamlit/test_secrets.toml"

with open("firestore-key.json") as json_file:
    json_text = json_file.read()

config = {"textkey": json_text}
toml_config = toml.dumps(config)

# 添加模型
with open(output_file, "a") as target:
    target.write(toml_config)
```
