#import "template.typ": *
#import "bytefield.typ": *
#show: LNCS-paper.with(
  title: "Transferência rápida e fiável de múltiplos servidores em simultâneo",
  subtitle: "Trabalho prático Nº2\nComunicações por Computador",
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
  bits: 32,
  bitheader: (0, 8, 24, 31),
  bits(8)[Type],
  bits(16)[Nº of files],
  bits(8)[File hash length],
  bits(40)[File hash],
  bits(8)[File name length],
  bits(24)[File name],
  bits(8)[Nº block sets],
  bits(16)[Division size],
  bits(16)[Size of the last block],
  bits(16)[Nº of blocks],
)

=== Atualização parcial dos ficheiros

#bytefield(
  bits: 32,
  bitheader: (0, 8, 24, 31),
  bits(8)[Type],
  bits(16)[Nº of files],
  bits(8)[File hash length],
  bits(40)[File hash],
  bits(8)[File name length],
  bits(24)[File name],
  bits(8)[Nº block sets],
  bits(16)[Division size],
  bits(16)[Size of the last block],
  bits(16)[Nº of blocks],
  bits(16)[Block number],
  bits(16)[Block number]
)

=== Resposta genérica

#bytefield(
  bits: 40,
  bitheader: (0, 8, 24, 39),
  bits(8)[Type], 
  bits(16)[Result status],
  bits(16)[Counter]

)

=== Pedido de saída

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
  bits: 40,
  bitheader: (0, 8, 16, 39),
  bits(8)[Type],
  bits(8)[File name length],
  bits(24)[File name],
)

=== Localizar ficheiro por hash

#bytefield(
  bits: 40,
  bitheader: (0, 8, 16, 39),
  bits(8)[Type],
  bits(8)[File hash length],
  bits(24)[File hash],
)

=== Resposta da localização de um ficheiro por nome

#bytefield(
  bits: 72,
  bitheader: (0, 8, 24, 32, 48, 56, 71),
  bits(8)[Type],
  bits(16)[Nº IPs],
  bits(32)[IPv4 address],
  bits(16)[Nº hashes],
  bits(8)[Hash length],
  bits(24)[File hash],
  bits(16)[Nº IPs],
  bits(16)[IP reference]
)

=== Resposta da localização de um ficheiro por hash

#bytefield(
  bits: 56,
  bits(8)[Type],
  bits(16)[Nº IPs],
  bits(32)[IPv4 address],
  bits(16)[Nº hashes],
  bits(8)[Hash length],
  bits(24)[File hash],
  bits(16)[Nº IPs],
  bits(16)[IP reference],
  bits(8)[Nº block sets],
  bits(16)[Division size],
  bits(16)[Last block size],
  bits(16)[Is full],
  bits(16)[Nº of blocks],
  bits(16)[Block number]

)

== Implementação

== Testes

= FS Transfer Protocol

== Motivação

== Vista geral

== Especificação

=== Dados iniciais

#bytefield(
  bits(8)[Type],
  bits(16)[Sequence number],
  bits(8)[File name length],
  bits(16)[File name],
  bits(16)[Division size],
  bits(16)[Block number],
  bits(32)[Data length],
  bits(16)[Data]
)

=== Dados

#bytefield(
  bits: 40,
  bits(8)[Type],
  bits(16)[Sequence number],
  bits(16)[Block number],
  bits(32)[Data length],
  bits(8)[Data]
)

=== Ack

#bytefield(
  bits: 24,
  bits(8)[Type],
  bits(16)[Ack number]
)

=== Pedido de um ficheiro completo

#bytefield(
  bits: 48,
  bits(8)[Type],
  bits(8)[Hash length],
  bits(16)[File hash],
  bits(16)[Division size]
)

=== Pedido de parte(s) de um ficheiro

#bytefield(
  bits: 48,
  bits(8)[Type],
  bits(8)[Hash length],
  bits(16)[File hash],
  bits(16)[Division size],
  bits(8)[Nº sequences],
  bits(16)[First],
  bits(16)[Last],
  bits(16)[Nº blocks],
  bits(16)[Block number]
)

== Implementação

== Testes

= Conclusões e trabalho futuro