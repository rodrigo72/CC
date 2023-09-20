# Draft do relatório para o TP1 de CC

## QUESTÕES (Parte I)

1. De que forma as perdas e duplicações de pacotes afetaram o desempenho das aplicações? Que camada lidou com as perdas e duplicações: transporte ou aplicação? Responda com base nas experiências feitas e nos resultados observados

Ao testar a conectividade entre o Portatil1 e o Servidor1 através do comando ping, observamos que não ocorreu perda de pacotes, i.e. foram enviadas 20 ICMP requests e foram recebidas 20 ICMP replies, e que a rota consistiu de links com capacidade ilimitada e capacidade de 1.0 Gbps com delay de 100 µs entre os switches e os routers, o que contribuiu para uma conexão sem perdas e duplicados - apesar disso, fatores como o congestionamento de rede poderiam interferir.

Por outro lado, ao testar a conectividade entre o PC1 e o Servidor1, também através do comando ping, observamos que ocorreu 20% de perda de pacotes (apenas 16 recebidos) e 3 duplicados, cuja causa está no link entre o Router4 e o Switch2 que possui uma largura de banda de 10 Mbps, um delay de 4 ms, uma probabilidade de perda de 10% e uma probabilidade de 5% de duplicação. Por este motivo, os protocolos da camada de transporte usados, o SFTP, FTP, TFTP e HTTP, apesar de possuírem métodos para lidar com a perda de pacotes e duplicados, acabam por fornecer um serviço mais lento à camada aplicacional. Por exemplo, quando se transferiu um ficheiro do Servidor1 para o PC1 utilizando SFTP (SSH File Transfer Protocol), a velocidade de transferência foi de 9.0 KB/s, enquanto que, quando se transferiu um ficheiro do Servidor1 para o Portatil1, a velocidade de transferência foi de 114.6 KB/s; e, quando se transferiu um ficheiro do Servidor1 para o PC1 utilizando FTP (File Transfer Protocol), a velocidade de transferência foi de 623.22 KB/s, enquanto que, quando se transferiu um ficheiro do Servidor1 para o Portatil1, a velocidade de transferência foi de 3.56 MB/s. 
Portanto, observa-se que existe uma diferença significativa entre velocidades de transferência do ficheiro devido às perdas de pacotes num dos links.

2. Obtenha a partir do wireshark, ou desenhe manualmente, um diagrama temporal para a transferência de file1 por FTP. Foque-se apenas na transferência de dados [ftp-data] e não na conexão de controlo, pois o FTP usa mais que uma conexão em simultâneo. Identifique, se aplicável, as fases de início de conexão, transferência de dados e fim de conexão. Identifique também os tipos de segmentos trocados e os números de sequência usados quer nos dados como nas confirmações.

3. Obtenha a partir do wireshark, ou desenhe manualmente, um diagrama temporal para a transferência de file1 por TFTP. Identifique, se aplicável, as fases de início de conexão, transferência de dados e fim de conexão. Identifique também os tipos de segmentos trocados e os números de sequência usados quer nos dados como nas confirmações.

4. Compare sucintamente as quatro aplicações de transferência de ficheiros que usou nos seguintes pontos (i) uso da camada de transporte; (ii) eficiência; (iii) complexidade; (iv) segurança;

## QUESTÕES (Parte II)

