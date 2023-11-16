#import "template.typ": *
#import "bytefield.typ": *
#show: LNCS-paper.with(
  title: "Transferência rápida e fiável de múltiplos servidores em simultâneo",
  subtitle: "Comunicações por Computador\nTrabalho prático Nº2",
  university: "Universidade do Minho, Departamento de Informática",
  email_type: "alunos.uminho.pt",
  authors: (
    (
      name: "Rodrigo Monteiro",
      number: "a100706",
    ),
    (
      name: "Diogo Abreu",
      number: "a100646",
    ),
    (
      name: "Miguel Gramoso",
      number: "a100845",
    )
  ),
  abstract: lorem(30),
  bibliography-file: "refs.bib",
)

= Introdução

= Arquitetura da solução


= FS Tracker Protocol

== Motivação


== Vista geral


== Especificação

=== Atualização dos ficheiros completos

#bytefield(
  bits: 40,
  bitheader: (0, 8, 24, 39),
  bits(8)[Type],
  bits(16)[Nº of files],
  bits(16)[File hash length],
  bits(40)[File hash],
  bits(16)[File name length],
  bits(24)[File name],
  bits(8)[Nº block sets],
  bits(16)[Division size],
  bits(16)[Size of the last block],
  bits(16)[Nº of blocks],
)

=== Atualização parcial dos ficheiros

#bytefield(
  bits: 40,
  bitheader: (0, 8, 24, 39),
  bits(8)[Type],
  bits(16)[Nº of files],
  bits(16)[File hash length],
  bits(40)[File hash],
  bits(16)[File name length],
  bits(24)[File name],
  bits(8)[Nº block sets],
  bits(16)[Division size],
  bits(16)[Size of the last block],
  bits(16)[Nº of blocks],
  bits(16)[Block],
  bits(16)[Block],
  bits(16)[Block],
  bits(16)[Block],
)

=== Resposta genérica

#bytefield(
  bits: 40,
  bitheader: (0, 8, 24, 39),
  bits(8)[Type], 
  bits(16)[Result status],
  bits(16)[Counter]

)

=== Pacote de saída

#bytefield(
  bits: 8,
  bitheader: (0, 7),
  bits(8)[Type],
)

=== Atualização de estado

#bytefield(
  bits: 16,
  bitheader: (0, 8, 15),
  bits(8)[Type],
  bits(8)[Status]
)

=== Verificação de estado

#bytefield(
  bits: 40,
  bitheader: (0, 8, 39),
  bits(8)[Type],
  bits(32)[IPv4 address],
)

=== Resposta de estado

#bytefield(
  bits: 32,
  bitheader: (0, 8, 16, 31),
  bits(8)[Type],
  bits(8)[Result],
  bits(16)[Counter]
)

=== Localizar ficheiro por nome

#bytefield(
  bits: 24,
  bitheader: (0, 8, 23),
  bits(8)[Type],
  bits(16)[File name length],
  bits(24)[File name],
)

== Localizar ficheiro por hash

== Implementação

== Testes

= FS Transfer Protocol

== Motivação

== Vista geral

== Especificação

== Implementação

== Testes

= Conclusões e trabalho futuro