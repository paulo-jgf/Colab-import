# -*- coding: utf-8 -*-
"""
Created on Wed Feb 12 14:17:14 2020

Este arquivo guardará os objetos de funções auxiliares para o código de diferença literal

@author: PAULO.GFERREIRA
"""

"""------ Pacotes ------"""
import unicodedata, re
from docx import Document
from datetime import datetime

"""------ Classes ------"""

# Objetos alterações encotradas
class Alteracoes_obj:
    #instancias_criadas = []    
    def __init__(self, ind_original=None, ind_novo=None, simi_difflib=None, simi_bow=None, tipo=None):
        self.ind_original = ind_original
        self.ind_novo = ind_novo
        self.simi_difflib = simi_difflib
        self.simi_bow = simi_bow
        self.tipo = tipo
        # Mantem uma lista de instancias da classe criadas, não funcionou com esperado
        #Alteracoes_obj.instancias_criadas.append(self)

    # Como o objeto da classe aparecerá
    def __repr__(self):
        boneco = "Obj Alt ('{}','{}','{}')"
        return boneco.format(str(self.tipo), str(self.ind_original), self.ind_novo)

# Objetos trechos de texto
class Trecho_obj:    
    def __init__(self, ind, conteudo):
        self.ind = ind
        self.conteudo = conteudo
        
    # Criar bow uma vez, para otimizar
    @property
    def bow(self, ref_re='[^a-zA-Z0-9/\- \\\]'): 
        return tuple([limpa_texto(t, ref_re).lower() for t in self.conteudo.split()])


"""------ Funções ------"""
# Prepara lista de obj de trecho de textos
def prepara_trechos_obj(texto, limpa_textos=False, minusculas=False, separador='.', alt_tokens=True):
    
    # O texto é uma string ou já veio separado?
    if isinstance(texto, str):
        # Separar só se houver separador, tratamento básico
        if separador:
            if limpa_textos: texto = limpa_texto(texto).strip()
            if minusculas: texto = texto.lower()
            # TODO Implementar Correção de números, versão web  
            trechos_texto = texto.split(separador)
            trechos_texto = [re.sub(' +', ' ',t).strip() for t in trechos_texto if t.strip()]
    
        else: alt_tokens=False        
        # Aprimoramento de tokens
        if alt_tokens and separador: trechos_texto = altera_tokenizacao_prox(trechos_texto, separador)
    
    # Se texto não for str então espera-se que ele já tenha vindo dividido
    else:
        trechos_texto = texto
        #TODO O mesmo tratamento pode acima pode ser aplicado aqui, implementar se necessário
        
    # Cria objs trecho no return
    return tuple([Trecho_obj(i, trechos_texto[i]) for i in range(len(trechos_texto))])

# Limpa parags
def limpa_texto(texto, remove_acento=False, ref_re='[^a-zA-Z0-9/\-.,;çÇàÀãÃõÕâÂôÔêÊáÁéÉíÍóÓúÚüÜ \\\]'):
    texto = re.sub(' +', ' ', texto)    
    # Texto integro 
    texto = re.sub(ref_re, '', texto)    
    if not remove_acento: return texto

    # Unicode normalize transforma um caracter em seu equivalente em latin.
    nfkd = unicodedata.normalize('NFKD', texto)
    texto_sem_acento = u"".join([c for c in nfkd if not unicodedata.combining(c)]) 

    # Tira acento e esquisitos
    texto_sem_acento = re.sub('[^a-zA-Z0-9/\-.,; \\\]', '', texto_sem_acento)
    
    # UTF-8 sem acento e espaçamento duplo
    return texto_sem_acento

# Mais uma função para melhorar resultados
def trata_numeros(texto):
    fim_frase = texto[-2:]
    texto = texto[:-2]
    numeros = re.compile('((\d)+(\.)(\d)?)', re.VERBOSE)
    f_iter = numeros.finditer(texto)
    for encontrado in f_iter:
        i, f = encontrado.span()[0], encontrado.span()[1]

        if encontrado.group()[-1] in ['.','$']:
            texto = texto[:i] + re.sub('\.',' ', texto[i:f]) + texto[f:]
        else:
            texto = texto[:i] + re.sub('\.','¢', texto[i:f]) + texto[f:]
    # Limpa sobra junta fim
    return re.sub(' +', ' ', texto) + fim_frase

# Função que importa do word
def importa_textos_parags_word(arquivo, limpa_textos=True, minusculas=False, separador_custom=False, alt_tokens=False):
    print(re.sub(':','.',str(datetime.now())[2:-7])+': Importando arquivo'+arquivo+'...')
    
    doc = Document(arquivo)
    paragrafos_arquivo = []
    
    if separador_custom=='.': altera_numeros = True
    else: altera_numeros = False
    
    for parag in doc.paragraphs:
        if limpa_textos: paragrafo = limpa_texto(parag.text).strip()
        if minusculas: paragrafo = paragrafo.lower()               
        # Esta linha se livra das strings vazias, e dá um tratamento nos números
        if paragrafo:
            if altera_numeros: paragrafo = trata_numeros(paragrafo)
            paragrafos_arquivo.append(paragrafo)

    # Em vez de separar por paragraphs do Docx, separa por outros caracteres. O ponto é o default
    if separador_custom:
        paragrafos_arquivo = ' '.join(paragrafos_arquivo)                
        trechos_texto = [re.sub(' +', ' ',t).strip() for t in paragrafos_arquivo.split(separador_custom) if t.strip()]
    
        # Aprimoramento de tokens
        if alt_tokens: trechos_texto = altera_tokenizacao_prox(trechos_texto, separador_custom)

    # Cria objs trecho, tem um gato aqui pra lidar com o tratamento de números
    objs_trechos = tuple([Trecho_obj(i, re.sub('¢',r'.',trechos_texto[i])) for i in range(len(trechos_texto))])
    
    print('  Concluído às:', re.sub(':','.',str(datetime.now())[2:-7]).split()[1])        
    return objs_trechos

# A divisão por ponto final pode gerar divisão demais, eis uma tentativa de reduzir a dimensionalidade        
def altera_tokenizacao_prox(trechos, sep):
    print(re.sub(':','.',str(datetime.now())[2:-7])+': Corrigindo tokens...')   
    # Decide quem deve ser removido
    #remover = [i for i in range(len(trechos)) if ' ' not in trechos[i]]
    remover = [i for i in range(len(trechos)) if trechos[i].count(' ') < 3]
    aux = remover.copy()
    
    for i in range(len(aux)):
        if aux[i] < len(trechos) - 1:
            # Junta ao proximo        
            trechos[aux[i] + 1] = trechos[aux[i]] +sep+ trechos[aux[i] + 1]
        
        # Se não houver proximo cai aqui, junta com o proximo    
        else:
            trechos[aux[i] - 1] = trechos[aux[i] - 1] +sep+ trechos[aux[i]]
            
    # Remove sobra
    for e in list(reversed(remover)):
        trechos.pop(e)        
    return trechos

# Retorna razão de palavras constantes dos bags
# Este valor pode dar 1.0, máximo, mesmo que os textos sejam diferentes,
# pois todas as palavras da bag1 podem estar contidas na bag2
def compara_bag_of_words(bag1, bag2):
    contidas = 0
    for palavra in bag1:
        if palavra in bag2:
            contidas += 1   
    # Retorna a razao de palavras contidas
    if len(bag1) > 0: return contidas/len(bag1)
    else: return 0
    
# Atualmente gera relatório txt
def gera_relat_txt(parags_originais, parags_novos, alteracoes,  incluidos, excluidos, cria_arquivo=True):
    print(re.sub(':','.',str(datetime.now())[2:-7])+': Escrevendo relatório...')
    
    # Faz um subcorte do trecho com base na diferença
    def sub_corte_trecho(original, novo):
        # Marca o começo
        for inicio in range(len(original)):
            try:
                if original[inicio] != novo[inicio]:
                    break
            except:
                # Se falhar foi out-of-range, então um está contido no outro
                inicio = min(len(original),len(novo))
                break            
        # Marca o fim
        dif_tamanho = len(original) - len(novo)
        for fim in range(len(original)-1,-1,-1):
            try:
                if original[fim] != novo[fim - dif_tamanho]:
                    # Adicionada demarcação da posição do melhor resultado
                    fim = fim - dif_tamanho + 1
                    break
            except:
                fim = False
                break

        # Se houver fim retorna bonito
        if fim or fim == 0:
            # Pode ser que a frase original esteja complemetamente contida na nova, sendo que a nova começa diferente
            if fim == 0 and dif_tamanho < 0: fim = fim + abs(dif_tamanho)
            
            return (original, novo[ : inicio] +'*'+ novo[inicio : fim] +'*'+ novo[fim : ])        
        return (original, novo[ : inicio] +'*'+ novo[inicio : ])
    
    # Relatório artesanal
    relatorio = +50*'*'+'\nRELATÓRIO DE ALTERAÇÕES\n\nO símbolo Asterisco (*) é uma tentativa de denotação do segmento alterado nos trechos diferentes\n'
    relatorio = relatorio +'Total trechos c/ nova versão: '+str(len(alteracoes))+'\nTotal trechos incluídos: '+str(len(incluidos))+'\nTotal trechos eliminados: '+str(len(excluidos))+'\n'+50*'*' 
    
    # Ver abaixo
    inds_alteracoes = [a.ind_original for a in alteracoes]
    inds_incluidos = [a.ind_novo for a in incluidos]
    inds_excluidos = [a.ind_original for a in excluidos]
    
    #TODO Dicionário alteração, para simplifcar o código se desejado for
    dicio_alts = {'Inc':'Paragrafo provavelmente adicionado',
                  'Exc':'Paragrafo provavelmente eliminado'}
    
    # Vamos tentar apresentar as ocorrências na ordem em que aparecem no texto
    ind_alteracoes_todas = sorted( list(set( inds_alteracoes + 
                                            inds_incluidos + 
                                            inds_excluidos)))
    
    # Se houver alteração discrimina
    if ind_alteracoes_todas: relatorio = relatorio +'\n\nAlterações discriminadas a seguir:\n'+50*'-'+'\n'
    
    # Novo algoritmo para mostrar ordenadamente as alterações
    ind_relatorio = 1
    for ind in ind_alteracoes_todas:
        # Procura alteracao de texto
        if ind in inds_alteracoes:           
            # Seleciona alteração
            for alt in alteracoes:
                if alt.ind_original == ind:
                    ind_novo = alt.ind_novo
                    inds_alteracoes.remove(ind)
                    break
            # Recorte
            original, novo = sub_corte_trecho(parags_originais[ind].conteudo, parags_novos[ind_novo].conteudo)
            relatorio = relatorio + 'Alt. {} ({} - {})\nO trecho: {}\n\nprovavelmente se tornou:\n\n{}\n\n'.format(
                    str(ind_relatorio),ind, ind_novo, original, novo) +50*'-'+'\n'
            ind_relatorio += 1
            
        # Inclusão de coisas novas
        if ind in inds_incluidos:
            relatorio = relatorio + 'Alt. {} ({})\nParagrafo provavelmente adicionado:\n'.format(str(ind_relatorio), str(ind))
            relatorio = relatorio + parags_novos[ind].conteudo +'\n\n'+50*'-'+'\n'
            ind_relatorio += 1
            
        # Exclusão de coisas     
        if ind in inds_excluidos:
            relatorio = relatorio + 'Alt. {} ({})\nParagrafo provavelmente eliminado:\n'.format(str(ind_relatorio), str(ind))
            relatorio = relatorio + parags_originais[ind].conteudo +'\n\n'+50*'-'+'\n'
            ind_relatorio += 1
            
    # Escreve o txt
    if cria_arquivo:
        relatorio_txt = open('relatorio_comparaca.txt', 'w')
        relatorio_txt.write(relatorio)
        relatorio_txt.close()
        print('  Arquivo relatorio_comparaca.txt criado')
    
    print('  Concluído às:', re.sub(':','.',str(datetime.now())[2:-7]).split()[1])
    return relatorio














