# mansea · 本地命令手册检索

使用 Python 标准库实现的离线检索工具。为本机命令手册建立索引，以中英文查询检索说明、用法与相关命令；同时提供命令行入口、中文速查页和仅监听本机的网页服务。

## 运行

需要 Python 3.10 或更新版本，无需安装第三方依赖。

```bash
python3 -m mansea.cli --help
```

按照帮助中的 `build` 命令建立本机手册索引后，再运行 `search` 或 `serve`。

```bash
python3 -m mansea.cli build
python3 -m mansea.cli search "查找文件"
python3 -m mansea.cli serve
```

打开 http://127.0.0.1:8733 。`site/cheatsheet.html` 是无需语料的速查页；如需含全文的离线单文件页面，在建立索引后运行 `python3 -m mansea.build_static`，生成结果仅供你按语料许可使用。索引来自自己的系统手册，平台之间的可执行命令及手册内容会不同。

## 结构

`mansea/` 包含分词、BM25、查询扩展、排序与命令行；`site/` 为本机网页；`data/` 为运行时索引。公开源码应排除原工作日志、会话目录、运行日志与本机语料索引。预构建离线页面包含本机手册全文，再分发前需单独核验语料许可。

网页服务只监听 `127.0.0.1`，静态请求经过 URL 解码与路径边界检查，禁止访问站点目录外的文件和越界符号链接。本工具用于查阅命令，不会代替你执行搜索结果中的命令。

## 验证

```bash
python3 -m unittest discover -s tests -v
```

现有检索自检可通过 `python3 -m mansea.smoke` 运行，需先建立索引。检索质量指标依赖本机语料与对应测试集，不能当作跨系统性能保证。
