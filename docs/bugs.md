# Bugs 6/7

- 本地模式，点文章的history，没反应。
  - 报错：Cannot reach server. Is the backend running on port 8080?
  - 问题是draft有没有新建仓库？draft应该新建，不然无法更新历史。
  - 点保存的时候就应该是一个commit，必须要填commit message。
- 文章页面的作者显示：516bcc05-62ea-4cf6-8fc3-1bdb36033407
  - 没有作者名字
- 文章页面点source变成白屏

# Bugs 6/8

- 本地模式的直接点编辑会出来之前的历史，不是崭新的文档，这个问题之前也发生过，但是有新的改动之后就又出现了
- 本地模式的新建文章的编辑右上角没有历史图标，但是如果从用户主页进去，又有了