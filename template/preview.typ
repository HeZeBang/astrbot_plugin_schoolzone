// 投稿预览卡片模板
// 通过 sys.inputs 传入参数:
//   author:    投稿者名称（空字符串则不显示）
//   content:   投稿文本内容
//   img_files: 图片文件名列表，逗号分隔（如 "img_0.png,img_1.jpg"）

#let author = sys.inputs.at("author", default: "")
#let content = sys.inputs.at("content", default: "")
#let img-files-raw = sys.inputs.at("img_files", default: "")
#let img-files = if img-files-raw == "" { () } else { img-files-raw.split(",") }
#let img-count = img-files.len()

#set page(width: 400pt, height: auto, margin: 16pt)
#set text(font: "Noto Sans SC", size: 13pt, fill: rgb("#0f1419"))

#block(
  width: 100%,
  inset: 20pt,
  radius: 12pt,
  stroke: 1pt + rgb("#e1e8ed"),
  fill: white,
)[
  // ── 头部：作者 ──
  #if author != "" {
    text(size: 14pt, weight: "bold")[#author]
    h(6pt)
    text(size: 12pt, fill: rgb("#536471"))[· 投稿预览]
  } else {
    text(size: 14pt, weight: "bold", fill: rgb("#536471"))[投稿预览]
  }

  #v(10pt)

  // ── 正文 ──
  #if content != "" {
    let lines = content.split("\n")
    for (i, line) in lines.enumerate() {
      [#line]
      if i < lines.len() - 1 {
        linebreak()
      }
    }
  } else {
    text(fill: rgb("#536471"))[(无文字)]
  }

  // ── 图片 ──
  #if img-count > 0 {
    v(12pt)

    if img-count == 1 {
      block(clip: true, radius: 12pt, width: 100%)[
        #image(img-files.at(0), width: 100%)
      ]
    } else if img-count == 2 {
      grid(
        columns: (1fr, 1fr),
        gutter: 4pt,
        block(clip: true, radius: 8pt)[#image(img-files.at(0), width: 100%)],
        block(clip: true, radius: 8pt)[#image(img-files.at(1), width: 100%)],
      )
    } else if img-count == 3 {
      grid(
        columns: (1fr, 1fr),
        rows: 2,
        gutter: 4pt,
        grid.cell(rowspan: 2)[
          #block(clip: true, radius: 8pt, height: 100%)[
            #image(img-files.at(0), width: 100%, height: 100%, fit: "cover")
          ]
        ],
        block(clip: true, radius: 8pt)[#image(img-files.at(1), width: 100%)],
        block(clip: true, radius: 8pt)[#image(img-files.at(2), width: 100%)],
      )
    } else {
      // 4+ 张：2 列网格
      grid(
        columns: (1fr, 1fr),
        gutter: 4pt,
        ..img-files.map(f => {
          block(clip: true, radius: 8pt)[
            #image(f, width: 100%)
          ]
        })
      )
    }
  }

  // ── 底栏 ──
  #v(14pt)
  #line(length: 100%, stroke: 0.5pt + rgb("#eff3f4"))
  #v(8pt)
  #align(center)[
    #text(size: 10pt, fill: rgb("#536471"))[确认发布请发送 /确认，取消请发送 /取消]
  ]
]
