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
  bibliography-file: "refs.bib",
  bibliography-full: true
)

= Introdução

Neste projeto, é implementado um serviço de partilha de ficheiros _peer-to-peer_, em que uma transferência pode ser feita em paralelo por conjuntos de blocos.

Para isso, cada nodo executa uma aplicação designada por `FS_Node` que se conecta a um servidor de registo de conteúdos designado por `FS_Tracker`, informando-o dos seus ficheiros e blocos. Assim, quando um nodo pretende localizar e descarregar um ficheiro, interroga em primeiro lugar o `FS_Tracker`, depois utiliza um algoritmo de seleção de #emph("FS nodes"), e inicia a transferência por UDP com um ou mais nodos, sendo garantida uma entrega fiável. 

Para além disso, utiliza as seguintes tecnologias: Python3, sqlite3, bind9 e XubunCORE.

= Arquitetura da solução

== Divisão de ficheiros

Primeiramente, achamos necessário explicitar a nossa abordagem em relação à divisão de ficheiros e gestão de dados.

No `FS_Node`, é utilizada uma classe `File_manager` que é responsável por fazer a divisão dos ficheiros por blocos, de acordo com um determinado _division size_, e por guardar os dados acerca dos ficheiros e dos blocos em estruturas de dados.

#[
  #set text(size: 9pt)
```text
Files: { file_name, File ( name, path, hash,
    blocks: { division_size, 
      set( Block (division_size, size, number, path, is_last))
    }, is_complete: set(division_size))
}
```
]
Assim, cada bloco é guardado com as seguintes informações: _division size_, o tamanho que se escolheu para dividir o ficheiro; size, que pode ser igual ao _division size_ ou ao resto da divisão; _path_ e se é ou não o último bloco.

Cada ficheiro tem um nome, _path_, _hash_ única, calculada com _sha1_ a partir do conteúdo e do nome do ficheiro, dicionário de _sets_ de blocos, em que a _key_ é o _division size_, e um _set_ de _division sizes_ (com uma correspondente divisão completa).

== Base de dados

No `FS_Tracker`, os dados acerca dos ficheiros e dos blocos de cada nodo são guardados numa base de dados `sqlite3`, utilizando a classe `DB_manager`. Escolhemos `sqlite3` pois é de simples utilização e _thread-safe_.

#figure(
  kind: image,
  image("images/modelo_logico.png", width: 65%)
)

Portanto, os #emph("FS nodes") são identificados a partir do seu _host name_, e os ficheiros são identificados a partir da sua hash única. Para além disso, cada bloco está associado a apenas um ficheiro e presente em _N_ nodos, e cada nodo possui _M_ blocos. Sendo assim, um bloco é identificado com 4 atributos: `size`, `number`, `division_size`, e `File_hash`.

== Diagrama de classes simplificado

#figure(
  kind: image,
  image("images/diagrama_classes.png", width: 70%)
)

Assim, o `FS_Node` também possui um _controller_ que permite receber e gerir _input_ do utilizador, e um dicionário de `UDP_connection`.

= FS Tracker Protocol

== Especificação

=== Atualização parcial e completa dos ficheiros

A seguinte tabela explica a mensagem protocolar utilizada para atualizar o #emph("FS Tracker") acerca dos ficheiros completos de um nodo.

#figure(
  kind: table,
  table(
    columns: (4fr,) + (2.5fr,) + (9fr,),
    stroke: (dash: "densely-dotted", thickness: 0.75pt), 
    align: (x, y) => left,
    [*Campo*], [*Tamanho (bytes)*], [*Descrição*],
    [Type], [1], [Tipo da mensagem enviada (`UPDATE_FULL_FILES = 0`).],
    [Nº of files], [2], [Número de ficheiros completos.],
    [File hash length], [1], [Comprimento da hash.],
    [File hash], [Variável], [Hash do ficheiro em formato binário.],
    [File name length], [1], [Comprimento do nome do ficheiro.],
    [File name], [Variável], [Nome do ficheiro em formato binário.],
    [Nº of block sets], [1], [Quantidade de conjuntos de blocos -- um nodo pode ter o mesmo ficheiro dividido de maneiras diferentes, i.e., com tamanhos de divisão diferentes.],
    [Division size], [2], [Valor do divisor.],
    [Last block size], [2], [Tamanho do último bloco, ou seja, do resto da divisão, ou o valor do divisor caso o resto seja 0.],
    [Nº of blocks], [2], [Número total de blocos resultantes da divisão.],
  )
)

A mensagem protocolar utilizada para fazer uma atualização parcial dos ficheiros de um nodo é semelhante à detalhada na tabela acima, sendo que a diferença está no _type_ (`UPDATE_PARTIAL = 1`) e no _Nº of blocks_ não ser o número de blocos total, mas o número de blocos que serão a seguir identificados no protocolo.

#figure(
  kind: table,
  table(
    columns: (4fr,) + (2.5fr,) + (9fr,),
    stroke: (dash: "densely-dotted", thickness: 0.75pt), 
    align: (x, y) => left,
    [Nº of blocks], [2], [Número de blocos que serão identificados.],
    [Block number], [2], [Número do bloco.]
  )
)

Assim, dizer que um bloco é, por exemplo, o nº 3, com uma divisão por 512 bytes, é equivalente a dizer que tem um _offset_ de 1536 bytes, e tamanho igual a 512 bytes (ou ao valor do _last block size_).

#pagebreak()

=== Resposta genérica

Uma resposta genérica do #emph("FS Tracker"), i.e., que é enviada como resposta associada a mais do que um tipo de pedido (de saída e de atualização). (_type_: `RESPONSE = 8`).

#bytefield(
  bits: 40,
  bitheader: (0, 8, 24, 39),
  bits(8)[Type], 
  bits(16)[Result status],
  bits(16)[Counter]
)

O campo `counter` indica a número da mensagem a que o servidor está a responder (funcionalidade não utilizada na versão final do projeto), e o campo _result status_ contém uma das seguintes representações:
```py
class status(IntEnum):
    SUCCESS = 0
    INVALID_ACTION = 1
    NOT_FOUND = 2
    SERVER_ERROR = 3
```

=== Pedido de saída

Antes de terminar a conexão, o #emph("FS Node") envia um pedido de saída. (`LEAVE = 7`).
#bytefield(
  bits: 8,
  bitheader: (0, 7),
  bits(8)[Type],
)

=== Atualização de estado

Caso o #emph("FS Node") esteja a enviar blocos para _n_ nodos, então o seu estado equivale ao valor _n_. (_type:_ `UPDATE_STATUS = 3`).

#bytefield(
  bits: 16,
  bitheader: (0, 8, 15),
  bits(8)[Type],
  bits(8)[Status]
)

=== Verificação de estado

#figure(
  kind: table,
  table(
    columns: (4fr,) + (2.5fr,) + (9fr,),
    stroke: (dash: "densely-dotted", thickness: 0.75pt), 
    align: (x, y) => left,
    [Type], [1], [Tipo da mensagem (`CHECK_STATUS = 4`).],
    [Host name length], [1], [Tamanho do _host name_.],
    [Host name], [Variável], [_Host name_ em formato binário.]
  )
)

=== Resposta de estado

#bytefield(
  bits: 32,
  bitheader: (0, 8, 16, 31),
  bits(8)[Type (11)],
  bits(8)[Result],
  bits(16)[Counter]
)

#pagebreak()

=== Localizar ficheiro por nome

#figure(
  kind: table,
  table(
    columns: (4fr,) + (2.5fr,) + (9fr,),
    stroke: (dash: "densely-dotted", thickness: 0.75pt), 
    align: (x, y) => left,
    [Type], [1], [Tipo da mensagem (`LOCATE_NAME = 5`).],
    [File name length], [1], [Tamanho do nome do ficheiro.],
    [File name], [Variável], [Nome do ficheiro em formato binário.]
  )
)

=== Localizar ficheiro por hash

#figure(
  kind: table,
  table(
    columns: (4fr,) + (2.5fr,) + (9fr,),
    stroke: (dash: "densely-dotted", thickness: 0.75pt), 
    align: (x, y) => left,
    [Type], [1], [Tipo da mensagem (`LOCATE_HASH = 6`).],
    [File hash length], [1], [Tamanho da hash do ficheiro (utilizamos 20 bytes). ],
    [File hash], [Variável], [Hash do ficheiro em formato binário.]
  )
)

=== Resposta da localização de um ficheiro por nome

#figure(
  kind: table,
  table(
    columns: (4fr,) + (2.5fr,) + (9fr,),
    stroke: (dash: "densely-dotted", thickness: 0.75pt), 
    align: (x, y) => left,
    [Type], [1], [Tipo da mensagem \ (`RESPONSE_LOCATE_NAME = 10`).],
    [Nº of host names], [2], [Número de _host names_.],
    [Host name length], [1], [Comprimento do _host name_ (máximo 255 bytes).],
    [Host name], [Variável], [_Host name_, em formato binário, de um nodo que possui um ficheiro com o respetivo nome.],
    [Nº file hashes], [2], [Nº de _file hashes_.],
    [File hash length], [1], [Comprimento da hash do ficheiro.],
    [File hash], [Variável], [Hash do ficheiro em formato binário.],
    [Nº host names], [2], [Número de _host names_ que possuem um ficheiro com o respetivo nome e hash],
    [Host name reference], [2], [Referência (_index_) relativa aos _host names_ listados no início da mensagem.],
  )
)

#underline("Exemplo"): `(10, 3, 3, "PC1", 3, "PC2", 3, "PC3", 2, 20, <hash1>, 2, 1, 2, 20, <hash2>, 1, 3)` -- três nodos possuem um ficheiro com o respetivo nome, no entanto, esse nome está associado a duas `hashes` diferentes, sendo que os nodos `PC1` e `PC2` possuem o ficheiro com a `<hash1>` e o nodo `PC3` possui o ficheiro com a `<hash2>`.

#pagebreak()

=== Resposta da localização de um ficheiro por hash

#figure(
  kind: table,
  table(
    columns: (4fr,) + (2.5fr,) + (9fr,),
    stroke: (dash: "densely-dotted", thickness: 0.75pt), 
    align: (x, y) => left,
    [Type], [1], [Tipo da mensagem \ (`RESPONSE_LOCATE_HASH = 9`).],
    [Nº of host names], [2], [Número de _host names_.],
    [Host name length], [1], [Comprimento do _host name_.],
    [Host name], [Variável], [_Host name_, em formato binário, de um nodo que possui um ficheiro com a correspondente hash.],
    [Nº of sets], [1], [Nº de conjuntos de diferentes divisões que o nodo tem para o ficheiro correspondente.],
    [Division size], [2], [Valor do divisor.],
    [Last block size], [2], [Tamanho do último bloco.],
    [Full], [2], [Caso o nodo tenha o ficheiro completo, este campo terá o nº total de blocos, e será o último campo da mensagem. Caso contrário, este campo terá valor 0 e serão adicionados os seguintes campos.],
    [Nº of blocks], [2], [Número de blocos que serão identificados.],
    [Block number], [2], [Número do bloco.]
  )
)

#underline("Exemplo"): `(9, 2, 3, "PC1", 1, 512, 21, 0, 3, 1, 3, 4, 3, "PC2", 1, 1024, 210, 7)` -- dois nodos possuem o ficheiro com a hash correspondente, um possui parte do ficheiro, com _division size_ igual a 512 bytes, _last block size_ igual a 21, e blocos 1, 3, e 4, e o outro possui o ficheiro completo com _division size_ igual a 1024 bytes, _last block size_ igual 210 bytes, e nº total de blocos igual a 7.

== Implementação

=== FS_Tracker

O `FS_Tracker` cria uma `thread` por `FS_Node` (`thread-per-client`).
```py
while not self.done:
  client, address = self.socket.accept()
  host_name, _, _ = socket.gethostbyaddr(address[0])
  
  node_thread = Thread(
      target=self.listen_to_client,
      args=(client, host_name)
  )
  
  node_thread.start()
```

A função `listen_to_client` lê o primeiro byte, e chama uma função _handler_ de acordo com o tipo da mensagem recebida. Essa função desserializa a mensagem, chama uma função que atualiza ou faz uma _query_ à base de dados, e envia uma resposta.

#underline("Exemplo:")

```py
def handle_locate_hash_request(self, client, host_name, counter):
        file_hash = self.receive_file_hash(client)
        
        results, status_db = 
          self.db.locate_file_hash(file_hash, host_name)
        
        if status_db != status.SUCCESS.value:
            self.send_response(client, status_db, counter)
            return
        
        response = self.encode_locate_hash_response(results, counter)
        client.sendall(response)
```

Neste caso, a função `handle_locate_hash_request` desserializa o resto da mensagem (no código utilizamos os termos `decode` e `encode`), chama uma função da classe `DB_manager` que faz uma _query_ à base de dados:

```py
def locate_file_hash(self, file_hash, host_name):
  try:
      self.conn.execute("BEGIN")
      query = " ... "
      self.cursor.execute(query, (file_hash, host_name))
      results = self.cursor.fetchall()          
      self.conn.commit()
      return results, utils.status.SUCCESS.value
  except Error as e:
      self.conn.rollback()
      return None, utils.status.SERVER_ERROR.value
```

De seguida, caso não tenha ocorrido erro, é chamada a função `encode_locate_hash_response` para serializar a resposta, de acordo com os resultados obtidos e com o protocolo definido. Caso contrário, é enviada uma resposta genérica, com o _status_ retornado pela função `locate_file_hash`.

=== FS_Node

A inicialização do `FS_Node` é feita da seguinte maneira:

```py
args = parse_args()
fs_node_1 = FS_Node( ... )
fs_node_1.file_manager.run()

node_controller = FS_Node_controller(fs_node_1)
node_controller_thread = threading.Thread(target=node_controller.run)
node_controller_thread.start()
```

Assim, continuando o #underline("exemplo") anterior, mas na perspetiva do `FS_Node`, o utilizador decide procurar um ficheiro por hash:

```py
elif command == "locate hash" or command == "lh":
    file_hash = input("Enter file hash: ")
    self.node.send_locate_hash_request(file_hash)
    output = self.node.response_queue.get()
    print_locate_hash_output(output)
```

Assim, é chamada a função `send_locate_hash_request`, que chama uma função de serialização, e que envia a mensagem ao `FS_Tracker` para localizar a hash introduzida.
De seguida, espera que uma resposta seja adicionada à _queue_. A função que irá adicionar uma resposta à _queue_ será a `handle_locate_hash_response` caso não tenha ocorrido um erro no `FS_Tracker`, caso contrário, será a `handle_response`.

O funcionamento é muito semelhante para os outros tipos de `requests`, com exceção dos métodos de serialização e desserialização, que podem ser complexos -- o protocolo é eficiente em troca de mais computação na serialização e desserialização.

== Testes

#figure(
  kind: image,
  image("images/tracker_test.png", width: 99%)
)

Esta é uma demonstração simples do funcionamento do `FS Track Protocol`, que envolve apenas dois nodos, o "Portatil1" e o "PC1", um servidor de resolução de nomes, "Servidor1", e o #emph("FS tracker"), "Servidor2".

Primeiramente, é iniciado o servidor de resolução de nomes, e de seguida o #emph("FS tracker") com `python3 fs_tracker.py -d` (_debug_).
Depois, são iniciados os nodos com `python3 fs_node.py -a 10.4.4.2 -D ./data/n1 -d` e `python3 fs_node.py -a 10.4.4.2 -D ./data/n2 -d`. O nodo "PC1" informa o #emph("FS tracker") de todos os seus ficheiros e blocos com o comando `full update`, e recebe uma resposta com estado `SUCCESS`.

De modo a verificar se o #emph("FS tracker") realmente recebeu e armazenou a informação recebida, o "Portatil1" insere o comando `locate name lusiadas.txt` -- um ficheiro que o "PC1" possui. E recebe então uma resposta com a hash e com o _host name_ "PC1.cc2023".

= FS Transfer Protocol

== Especificação

=== Dados iniciais

#figure(
  kind: table,
  table(
    columns: (4fr,) + (2.5fr,) + (9fr,),
    stroke: (dash: "densely-dotted", thickness: 0.75pt), 
    align: (x, y) => left,
    [*Campo*], [*Tamanho (bytes)*], [*Descrição*],
    [Type], [1], [Tipo da mensagem enviada \ (`START_DATA = 0`).],
    [Sequence number], [2], [Número de sequência da mensagem (geralmente `1`).],
    [File name length], [1], [Comprimento do nome do ficheiro.],
    [File name], [Variável], [Nome do ficheiro em formato binário.],
    [Division size], [2], [Valor do divisor.],
    [Block number], [2], [Número do bloco a enviar (pode não ser 1).],
    [Data length], [4], [Tamanho dos dados a enviar.],
    [Data], [Variável], [Dados em formato binário],
  )
)

#pagebreak()

=== Dados

#figure(
  kind: table,
  table(
    columns: (4fr,) + (2.5fr,) + (9fr,),
    stroke: (dash: "densely-dotted", thickness: 0.75pt), 
    align: (x, y) => left,
    [Type], [1], [Tipo da mensagem enviada \ (`DATA = 0`, ou `END_DATA = 1`).],
    [Sequence number], [2], [Número de sequência.],
    [Block number], [2], [Número do bloco a enviar.],
    [Data length], [4], [Tamanho dos dados a enviar.],
    [Data], [Variável], [Dados em formato binário],
  )
)

=== Ack

#bytefield(
  bits: 24,
  bitheader: (0, 8, 23),
  bits(8)[Type],
  bits(16)[Ack number]
)

=== Pedido de um ficheiro completo

#figure(
  kind: table,
  table(
    columns: (4fr,) + (2.5fr,) + (9fr,),
    stroke: (dash: "densely-dotted", thickness: 0.75pt), 
    align: (x, y) => left,
    [Type], [1], [Tipo da mensagem enviada \ (`GET_FULL_FILE = 0`).],
    [File hash length], [1], [Comprimento da hash do ficheiro.],
    [File hash], [Variável], [Hash do ficheiro em formato binário.],
    [Division size], [2], [Valor de _division size_ escolhido.],
  )
)

=== Pedido de parte(s) de um ficheiro

Optamos por incluir sequências neste protocolo para transmitir a mesma quantidade de informação com uma quantidade significativamente menor de bytes.

#figure(
  kind: table,
  table(
    columns: (4fr,) + (2.5fr,) + (9fr,),
    stroke: (dash: "densely-dotted", thickness: 0.75pt), 
    align: (x, y) => left,
    [Type], [1], [Tipo da mensagem enviada \ (`GET_PARTIAL_FILE = 5`).],
    [Hash length], [1], [Comprimento da hash do ficheiro],
    [File hash], [Variável], [Hash do ficheiro em formato binário.],
    [Division size], [2], [Valor de _division size_ escolhido.],
    [Nº of sequences], [1], [O pedido pode conter [0, N] sequências de blocos.],
    [First], [2], [Número do primeiro bloco da sequência.],
    [Last], [2], [Número do último bloco da sequência.],
    [Nº of blocks], [2], [Número de blocos que não estão presentes nas sequências.],
    [Block number], [2], [Número do bloco.],
  )
)

== Implementação

Cada nodo possui uma _thread_ que fica a "ouvir" por mensagens UDP, uma classe `UDP_receiver_connection` -- que guarda dados acerca de uma transferência em curso, gere os números de sequência recebidos e retorna o _ack_ que é necessário enviar, -- um dicionário de _queues_ de _acks_ que as _threads_ responsáveis por enviar blocos utilizam, e um algoritmo de seleção de nodos.

A função que determina o próximo _ack number_ verifica se o número de sequência recebido é o esperado, e retorna um _ack number_ de acordo com números de sequência que recebeu. Por exemplo, caso esteja à espera do número de sequência `5`, e receba os números `7`, `8` e `9`, irá retornar `6` até o receber, e quando o receber irá retornar `10`.

```py
def ack(self, seq_num, block_number, is_last, data):
  if (seq_num > self.cur_seq_n and seq_num <= self.cur_seq_n + self.buff):
      self.seq_nums.add(seq_num)
      for n in sorted(self.seq_nums):
          if n == self.cur_seq_n + 1:
              self.cur_seq_n += 1  
              self.seq_nums.remove(n)
          else:
              break  # out of order seq_num
  return self.cur_seq_n + 1
```

Quando recebe um pedido de transferência completa ou parcial de um ficheiro, é criada uma nova _thread_ que corre a função `send_udp_blocks`, que envia um bloco e espera por um _ack_ com um limite de 500 ms. Caso o ack não seja recebido dentro do limite de tempo, o bloco é enviado novamente. Caso seja recebido, e seja o esperado, é enviado o próximo bloco.

```py
self.udp_socket.sendto(packet, address)
expected_ack = seq_num + 1
while max_timeout_retries:
    received_ack = self.udp_ack_queue.get(address, self.udp_ack_timeout)
    if received_ack is not None:
        if received_ack == expected_ack:
            break
    else:
        max_timeout_retries -= 1
        self.udp_socket.sendto(packet, address)
```

Para efetuar a transferência de um ficheiro, o utilizador usa o comando `get` e introduz a hash, depois, o _controller_ interroga o _FS Tracker_ acerca dos nodos que possuem um ficheiro com essa hash. Caso existam, chama uma função que seleciona nodos e que encarrega blocos a esses nodos -- utilizamos um algoritmo simples tenta atribuir a mesma quantidade de blocos a cada nodo. De seguida, são enviados os pedidos de transferência de partes de ficheiros.

#figure(
  kind: image,
  image("images/transferencia_udp.png", width: 50%)
)

== Testes

Três nodos têm o ficheiro `lusiadas.txt`, ou seja, todos menos o `Portatil1`. Assim, de modo a testar a transferência por UDP, executou-se o comando `get` no `Portatil1`, o que originou três transferências em paralelo, cada uma de 213 blocos de 512 bytes. Quando uma das transferências acaba, o _FS Tracker_ é atualizado, e, quando todas acabam, os blocos são unidos num só ficheiro.

#figure(
  kind: image,
  image("images/udp_test1.png", width: 100%)
)

#figure(
  kind: image,
  image("images/udp_test2.png", width: 100%)
)

#pagebreak()

= DNS

== Forward DNS bind9 configuration

```text
$TTL  86400
@            IN    SOA    Servidor1.cc2023.    admin.cc2023. (
                              1      ; Serial
                         604800      ; Refresh
                          86400      ; Retry
                        2419200      ; Expire
                          86400 )    ; Negative Cache TTL
@            IN    NS     Servidor1.cc2023.
Servidor1    IN    A      10.4.4.1
Servidor2    IN    A      10.4.4.2
Portatil1    IN    A      10.1.1.1
Portatil2    IN    A      10.1.1.2
PC1          IN    A      10.2.2.1
PC2          IN    A      10.2.2.2
Roma         IN    A      10.3.3.1
Paris        IN    A      10.3.3.2
```

== Reverse DNS bind9 configuration

```text
$TTL  86400
@            IN    SOA    Servidor1.cc2023.   admin.cc2023. (
                              1      ; Serial
                         604800      ; Refresh
                          86400      ; Retry
                        2419200      ; Expire
                          86400 )    ; Negative Cache TTL
@            IN    NS     Servidor1.cc2023.
1.1.1        IN    PTR    Portatil1.cc2023.
2.1.1        IN    PTR    Portatil2.cc2023.
1.2.2        IN    PTR    PC1.cc2023.
2.2.2        IN    PTR    PC2.cc2023.
1.3.3        IN    PTR    Roma.cc2023.
2.3.3        IN    PTR    Paris.cc2023.
1.4.4        IN    PTR    Servidor1.cc2023.
2.4.4        IN    PTR    Servidor2.cc2023.
```

== Default zones

```txt
zone "cc2023" {
    type master;
    file "/etc/bind/cc2023";
};

zone "10.in-addr.arpa" {
    type master;
    file "/etc/bind/cc2023reverse";
};
```

= Conclusões e trabalho futuro

#set list(marker: [--], indent: 7pt)

Para concluir, achamos que conseguimos implementar os requisitos fornecidos no enunciado, e por conseguinte, conseguimos entender o funcionamento de _sockets_ UDP e TCP, como construir un protocolo eficiente em formato binário, como lidar com perdas e duplicados numa transferência por UDP, como configurar um servidor DNS, entre outros.
No entanto, existe um conjunto de funcionalidades que gostariamos de ter adicionado:

- Utilização de um método `noack` para a transferência de ficheiros;
- Solução para o caso de um nodo deixar de estar disponível a meio de uma transferência;
- Implementação de um `checksum` nos pacotes enviados por UDP -- não achamos estritamente necessáio implementar um, pois o protocolo UDP já possui `checksum`. 