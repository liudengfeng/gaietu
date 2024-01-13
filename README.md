# Gaietu [英语乐园]

Gaietu is an AI-powered, gamified English learning app that helps users improve their listening, speaking, reading, and writing skills.

Gaietu 是一个利用`AI` 技术和游戏化元素的英语学习app，旨在帮助用户全面提高听、说、读、写技能。

## Note

+ Windows环境
    - python https://www.python.org/downloads/windows/
+ Streamlit Community Cloud is built on Debian Linux. 
+ components.html中css、元素必须组合使用，不可分离

### `streamlit`

+ `on_click` 先执行
+ 认证部分参考：https://github.com/mkhorasani/Streamlit-DbInterface

### WSL2

#### 安装语音 SDK

+ WSL2环境中，请务必仔细阅读安装指引。[Install the Speech SDK](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/quickstarts/setup-platform?tabs=linux%2Cubuntu%2Cdotnetcli%2Cdotnet%2Cjre%2Cmaven%2Cnodejs%2Cmac%2Cpypi&pivots=programming-language-python)

#### GStreamer

语音`SDK`可以使用`GStreamer`来处理压缩的音频。 出于许可原因，`GStreamer`二进制文件未编译，也未与语音 SDK 关联。 需要安装一些依赖项和插件。

请查阅[安装指引](https://learn.microsoft.com/zh-cn/azure/ai-services/speech-service/how-to-use-codec-compressed-audio-input-streams?tabs=windows%2Cdebian%2Cjava-android%2Cterminal&pivots=programming-language-python)。

### 使用的网络资源
[图片搜索](https://serper.dev):The World's Fastest and Cheapest Google Search API