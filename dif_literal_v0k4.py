# -*- coding: utf-8 -*-
"""
Created on Sun Jan 12 17:42:51 2020

Este código se presta a resolver o problema de comparar versões do mesmo texto, para localizar
os trechos que foram alterados. O fato de serem versões do mesmo texto é uma condição fundamental 
para a aplicação deste código, não fazendo sentido aplicá-lo para textos que sejam sabidamente 
diferentes.

Parametros ajustáveis:
    range_comparacao: define o alcance da comparação de 'todos' para 'todos'
    valor entre 0.0 ou 1.0 definir o range em comparação ao percentual do conteudo do texto original
    valor inteiro define diretamente o range em unidades de 'paragrafos'
    default 0.3
    testado para texto bula de 1200~ 'paragrafos' não tem diferença entre 0.2 e 0.25, e pouca
    diferença para 0.1 com ganho significativo de tempo
    Dois mínimos duros: 1 (primeiros vizinhos) ou a diferença de quantidade de paragrafos
    
    peso_distancia:
    penalidade para reduzir pontuação dos matches com a distância
    valor entre 0.0 e 0.9, default 0.3

Índices de parágrafos e similaridade por difflib e bow são o sistema básico da lógica

Ordem da lógica:
- O número de paragrafos (ou subtextos) foi alterado?
- Faz comparação 1pra1 para eliminar aqueles que estão alinhados e iguais
    Compara do menor pro maior para evitar out of range
- Faz comparação de todos para todos para encontrar melhor alinhamento
- As métricas são difflib bow e proximidade dos indices de textos semelhantes

TODO
- Alt. 14 totalmente bugada Herceptin
- Tokenizador aprimorar?
- Paragrafos já escolhidos podem ser escolhidos novamente como melhor match para outro parag antigo -
    Será isto um problema?
- Avaliar inclusão de bidirecionalidade no bow e no sequence matcher, trará grande prejuízo ao tempo de exec

pacotes necessários:
    pip install python-docx
    
benchmark busca todos para todos v03g
benchmark escopo limitado v0h
benchmark objetos trecho, alteracoes v0k1, requer utils
benchmark objetos + escopo + correcao tokens v0k2
benchmark objetos + escopo + correcao tokens + correcoes numeros + bias nos trechos v0k3
0k4 adaptador webapp

@author: paulo
"""

import utils_dif_literal as ut
import difflib, re, heapq
from datetime import datetime 

# Cria uma espécie de ensemble para comparar o melhor resultado do bow com o difflib
# Vamos fazer também a escolha do melhor indice caso hajam textos repetidos
# Reparar que o indice do texto é o mesmo do indice do difflib nas listas de similaridade
# Isso ajuda e da mais trabalho ao mesmo tempo
# Há também uma métrica de peso com respeito a distancia do melhor trecho à posição original do trecho no texto
def ensemble_resultado_difflib_bow(similaridades_difflib, similaridades_bows, indice_original, peso_distancia=0.3):
    # Corrigindo valor peso distância
    peso_distancia = min(0.9, peso_distancia)
    
    # Se o max for 1.0 vamos agir diferente
    if max(similaridades_difflib) == 1.0:
        resultado1 = [i for i in range(len(similaridades_difflib)) if similaridades_difflib[i] > 0.9]    
    # Se não vamos pegar os indices dos 3 melhores dif lib por ordem
    else:
        # Preservando a ordem, do melhor pro pior
        resultado1 = sorted(range(len(similaridades_difflib)), key=lambda i: similaridades_difflib[i], reverse=True)[:3]
    
    # Vamos pegar os n melhores indices para os 3 maiores bows
    top3_bow = heapq.nlargest(3, similaridades_bows)
    resultado2 = []
    for j in range(len(similaridades_bows)):
        if similaridades_bows[j] in top3_bow:
            resultado2.append(j)
    
    # Ensemble bow difflib
    melhores_resultados = []    
    for resultado in resultado1:
        if resultado in resultado2: melhores_resultados.append(resultado)
        
    # Resultado sem nenhuma concordância
    if len(melhores_resultados) == 0: return False, False, False
                
    # Melhor cenário: os métodos concordam e apresentam resultado único    
    if len(melhores_resultados) == 1:
        melhor_resultado = melhores_resultados[0]
        return melhor_resultado, similaridades_difflib[melhor_resultado], similaridades_bows[melhor_resultado]
    
    # Vamos tentar resolver, incluindo um fator de proximidade entre os paragrafos
    # O mais proximo deve ser o melhor. Reparar que a ordem de qualidade sem distancia está mantida
    distancias, simi_distancias = [], []
    for resultado in melhores_resultados:
        distancias.append(abs(resultado - indice_original))
        simi_distancias.append(similaridades_difflib[resultado])
    dist_min_ind = distancias.index(min(distancias))
    
    # Vamos nos contentar com pegar o mais próximo como o melhor
    if not peso_distancia:
        melhor_resultado = melhores_resultados[dist_min_ind]
        return melhor_resultado, similaridades_difflib[melhor_resultado], similaridades_bows[melhor_resultado]

    # Se passar vamos fazer a conta mais complicada, modulando o peso com a distância
    #dist_max_ind = distancias.index(max(distancias)) 

    # Vamos aplicar um peso ponderado pela distancia maxima, mas para evitar dar muito valor ao mais
    # proximo quando as posições forem muito proximas, vamos pegar o fator referente a esta distancia
    # como o maximo entre 0 e 4
    fator_dist = max(4, max(distancias))
    for i in range(len(distancias)):
        simi_distancias[i] = simi_distancias[i] * (1.0 - (distancias[i]/fator_dist) * peso_distancia)

    melhor_resultado = melhores_resultados[simi_distancias.index(max(simi_distancias))]

    # Trocar similaridade bow por max(simi_distancias), se necessário               
    return melhor_resultado, similaridades_difflib[melhor_resultado], similaridades_bows[melhor_resultado]    

# Todos para todos, tentando alinhar os paragrafos.
def c_todos_para_todos_alinhamento(textos_1, textos_2, indices_parag_diferentes, range_comparacao=0.3):
    len_texto2 = len(textos_2)
    bias_medio = 0
    
    # Trabalhando o range_comparacao a partir do parametro
    if range_comparacao:
        range_comparacao=abs(range_comparacao)
        
        if isinstance(range_comparacao, float):
            # Esperando float entre 0.0 e 1.0
            range_comparacao = min(1.0, range_comparacao)
            # Transformando float em range
            range_comparacao = int(round( range_comparacao * len(textos_1) / 2))
            
        # Podemos receber um inteiro também! Definição direta do intervalo   
        else:
            range_comparacao = min(len_texto2, range_comparacao)

        # Vamos definir um minimo razoável para olhar em volta, o código não faz sentido 
        # se não puder pelo menos olhar os primeiros vizinhos, ao mesmo tempo vamos garantir
        # que a busca nunca deixe ninguém de fora nos extremos, definindo um range mínimo com 
        # base na diferença de quantidade de 'paragrafos'
        range_min = abs(len(textos_1) - len(textos_2)) 
        range_comparacao = max(max (1, range_min), range_comparacao)            
        
        print('  Range de comparação definido = +- '+str(range_comparacao))
        
        def define_intervalo_varredura(i, bias_medio=0):
            # Vamos somar 1 no superior para lidar com a questão dos intervalos abertos!
            inferior = i - range_comparacao + bias_medio
            superior = i + range_comparacao + 1 + bias_medio
            
            if inferior < 0:
                #superior = min(abs(i + range_comparacao), len_texto2)
                superior = min(2*range_comparacao + 1, len_texto2)
                return 0, superior
            
            if superior > len_texto2:
                #inferior = max(abs(i - range_comparacao), 0)
                inferior = max(len_texto2 - (2*range_comparacao) - 1, 0)
                return inferior, len_texto2
            
            return inferior, superior
    
    # Range não definido ou = 0 busca o arquivo inteiro    
    else:
        def define_intervalo_varredura(i, bias_medio):
            return 0, len_texto2
    
    # Compara agora os originais que não encontraram um igual com todos os novos
    melhores_pares = []        
    for i in indices_parag_diferentes:
        similaridades_difflib, similaridades_bows = [], []
        
        # Vamos limitar o escopo de varredura no documento novo, par aum intervalo definido do novo documento
        ini_var, fim_var = define_intervalo_varredura(i, bias_medio)
        
        # Gato: como usamos o indice de j como referência para o método, precisamos
        # inicialziar as variáveis estupidamente
        similaridades_difflib, similaridades_bows = [0.0 for j in range(len(textos_2))], [0.0 for j in range(len(textos_2))]
        
        # Vamos aplicar o bias também, o deslocamente relativo entre os textos conforme progressão
        for j in range(ini_var,fim_var):
            # Similaridade por ordem de carater
            #similaridades_difflib.append(difflib.SequenceMatcher(None, textos_1[i], textos_2[j]).ratio())
            similaridades_difflib[j] = difflib.SequenceMatcher(None, textos_1[i].conteudo, textos_2[j].conteudo).ratio()
            
            # Similaridade da bag of words
            #similaridades_bows.append(compara_bag_of_words(i, j))
            similaridades_bows[j] = ut.compara_bag_of_words(textos_1[i].bow, textos_2[j].bow)
        
        # Pega o valor máximo de similaridade
        similaridade_max = max(similaridades_difflib)
        simi_bows_max = max(similaridades_bows)
        
        # Vamos impor um mínimo de similaridade para considerar uma versão de frase já existente
        if similaridade_max < 0.50 or simi_bows_max < 0.05: continue
                   
        # Faz o ensemble dos métodos
        melhor_resultado, similaridade_dif, similaridade_bow = ensemble_resultado_difflib_bow(similaridades_difflib, similaridades_bows, i) 
        
        # Guarda apenas resultados validos
        if melhor_resultado or melhor_resultado == 0:
            # Se houver range de comparação limitado define o deslocamente medio
            if range_comparacao: bias_medio = int(round((bias_medio + (melhor_resultado - i))/4))
            # Cria objeto
            melhor_par = ut.Alteracoes_obj(i, melhor_resultado, similaridade_dif, similaridade_bow, 'Nova versão')
            melhores_pares.append((melhor_par))

    return melhores_pares

# Comparação emparelhada, 1 pra 1. textos_2 deve ser maior ou igual que textos_1
def compara_1pra1(textos_1, textos_2):
    # A sigla ON significa Original-Novo, que é a ordem de comparação
    indices_parag_diferentes, indices_ja_resolvidos = [], []    
    
    # Compara um pra um, quem for igual fica de fora. textos_2 deve ser maior que textos_1
    try:
        for i in range(0,len(textos_1)):
            similaridade = difflib.SequenceMatcher(None, textos_1[i].conteudo, textos_2[i].conteudo).quick_ratio()
            if similaridade != 1.0:
                indices_parag_diferentes.append(i)
            else: indices_ja_resolvidos.append(i)
    except:
        print('Constraint de tamanhos de listas não respeitados, comparação 1 pra 1.')
        raise SystemExit
        
    return indices_parag_diferentes, indices_ja_resolvidos

# Corpo principal do código, recebe lista dos textos originais list de strs e a lista dos novos
def compara_textos(parags_originais, parags_novos, range_comparacao):
    print(re.sub(':','.',str(datetime.now())[2:-7])+': Comparando textos...')
    
    # Criados paragrafos, destruidos paragrafos?
    num_novos = len(parags_novos) - len(parags_originais)
    
    # O menor deve ser comparado com o maior
    if num_novos >= 0:
        # Retorna resolvidos e não resolvidos
        indices_parag_diferentes, indices_ja_resolvidos = compara_1pra1(parags_originais, parags_novos)
        
    else:
        # Retorna resolvidos e não resolvidos
        indices_parag_diferentes, indices_ja_resolvidos = compara_1pra1(parags_novos, parags_originais)
        # Completando os indices faltantes, já que o texto original é maior
        indices_parag_diferentes = indices_parag_diferentes + [i for i in range(len(parags_novos), len(parags_novos)+ abs(num_novos))]

    # Compara todos para todos buscando os melhores, aqui é o coração do código
    # Sigla ON denota Original-Novo
    melhores_pares_ON = c_todos_para_todos_alinhamento(parags_originais, parags_novos, indices_parag_diferentes, range_comparacao)        
   
    # Vamos juntar os indices já resolvidos para cada texto, lembrando que o melhores_pares_ON segue
    # o padrão da classe
    indices_ja_resolvidos_O = indices_ja_resolvidos + [e.ind_original for e in melhores_pares_ON]
    indices_ja_resolvidos_N = indices_ja_resolvidos + [e.ind_novo for e in melhores_pares_ON]
    
    # Vamos preparar o resultado excluindo agora aquele que estão idênticos mas com outros índices, ou seja,
    # aqueles que tiverem similaridade = 1.0
    melhores_pares = [e for e in melhores_pares_ON if e.simi_difflib < 1.0]
    
    # Aqui vamos apresentar os indices que não encontraram um par.
    provavelmente_novos = [ut.Alteracoes_obj(ind_novo= i, tipo='Inc') for i in range(0,len(parags_novos)) if i not in indices_ja_resolvidos_N]    
    provavelmente_excluidos = [ut.Alteracoes_obj(ind_original= i, tipo='Exc') for i in range(0,len(parags_originais)) if i not in indices_ja_resolvidos_O]

    print('  Concluído às:', re.sub(':','.',str(datetime.now())[2:-7]).split()[1])
    return melhores_pares, provavelmente_novos, provavelmente_excluidos

# Receba do webapp
def resposta_web_app(texto_orig, texto_novo, limpa_textos=False, minusculas=False, separador='.', range_comparacao=10):
    # Prepara objetos
    parags_originais = ut.prepara_trechos_obj(texto_orig, limpa_textos, minusculas, separador, range_comparacao, alt_tokens=True)
    parags_novos = ut.prepara_trechos_obj(texto_novo, limpa_textos, minusculas, separador, range_comparacao, alt_tokens=True)
    # Processa e retorna relatório
    alteracoes, incluidos, excluidos = compara_textos(parags_originais, parags_novos, range_comparacao)
    return ut.gera_relat_txt(parags_originais, parags_novos, alteracoes,  incluidos, excluidos, cria_arquivo=False)


# Chamamentos
if __name__ == '__main__':
    parags_originais = ut.importa_textos_parags_word(arquivo='herceptin bula 1.docx', separador_custom='.',alt_tokens=True)
    parags_novos = ut.importa_textos_parags_word(arquivo='herceptin bula 2.docx', separador_custom='.',alt_tokens=True)
       
    alteracoes, incluidos, excluidos = compara_textos(parags_originais, parags_novos, range_comparacao=10)
    
    relatorio = ut.gera_relat_txt(parags_originais, parags_novos, alteracoes,  incluidos, excluidos)



#'herceptin bula 1.docx'
#'herceptin bula 2.docx'
#'Texto_antes.docx'
#'Texto_depois.docx'




























