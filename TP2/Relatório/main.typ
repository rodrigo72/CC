#import "cover.typ": cover
#import "template.typ": *

#show: project

#cover(title: "[Inserir título aqui]", authors: (
  (name: "Rodrigo Monteiro", number: "a100706"), 
  (name: "Diogo Abreu", number: "a100646"), 
  (name: "Miguel Gramoso", number: "a100845")), 
  "Outubro, 2023")

#set page(numbering: "i", number-align: center)
#counter(page).update(1)

#heading(numbering: none, outlined: false)[Resumo]
<\<O resumo tem como objectivo descrever de forma sucinta o trabalho realizado. Deverá conter uma pequena introdução, seguida por uma breve descrição do trabalho realizado e terminando com uma indicação sumária do seu estado final. Não deverá exceder as 400 palavras.>>   

\

*Área de Aplicação*: <\<Identificação da Área de trabalho. Por exemplo: Desenho e arquitectura de Sistemas de Bases de Dados.>>

*Palavras-Chave*: <\<Conjunto de palavras-chave que permitirão referenciar domínios de conhecimento, tecnologias, estratégias, etc., directa ou indirectamente referidos no relatório. Por exemplo: Bases de Dados Relacionais, Gestão de Índices, JAVA, Protocolos de Comunicação.>>

#show outline: it => {
    show heading: set text(size: 18pt)
    it
}

#{
  show outline.entry.where(level: 1): it => {
    v(5pt)
    strong(it)
  }

  outline(
    title: [Índice], 
    indent: true, 
  )
}

#v(-0.4em)
#outline(
  title: none,
  target: figure.where(kind: "attachment"),
  indent: n => 1em,
)

#outline(
  title: [Lista de Figuras],
  target: figure.where(kind: image),
)

#outline(
  title: [Lista de Tabelas],
  target: figure.where(kind: table),
)

// Make the page counter reset to 1
#set page(numbering: "1", number-align: center)
#counter(page).update(1)

= FS Track Protocol

#table(
  columns: 3,
  "Type"
)
= Conclusões

// #heading(numbering: none)[Referências]
#bibliography("refs.bib", title: "Referências")

// #heading(numbering: none)[Lista de Siglas e Acrónimos]

#heading(numbering: none)[Anexos]