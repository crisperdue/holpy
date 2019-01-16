import io,sys
import json


def save_file(name, d):
    file_path = 'library/' + name + '.json'
    with open(file_path, 'r+', encoding='utf-8') as f:
        file_data = json.load(f)
        if file_data !=d:
            d = file_data + d
            j = open(file_path, 'w+', encoding='utf-8')
            json.dump(d, j, indent=4, ensure_ascii=False)
            j.close()
        f.close()

def save_proof(n, i, d, num_gaps):
    file_path = 'library/' + n + '.json'
    with open(file_path, 'r+', encoding='utf-8') as f:
        file_data = json.load(f)
        file_data[i]['proof'] = d
        file_data[i]['num_gaps'] = num_gaps
        j = open(file_path, 'w+', encoding='utf-8')
        json.dump(file_data, j, indent=4, ensure_ascii=False)
        j.close()
        f.close()

def save_edit(name, data, n, ty):
    file_path = 'library/' + name + '.json'
    n = int(n)
    with open(file_path,'r+',encoding='utf-8') as f:
        file_data = json.load(f)
        if ty == 'constant':
            file_data[n]['T']=data
        if ty == 'therom':
            file_data[n]['prop'] = data
        if ty == 'datatype':
            file_data[n]['']=''
        if ty == 'fun':
            file_data[n]['type'] = ''
        j = open(file_path, 'w+' ,encoding='utf-8')
        json.dump(file_data, j, indent=4, ensure_ascii=False)
        j.close()
        f.close()

def delete(name, n):
    file_path = 'library/' + name + '.json'
    with open(file_path, 'r+', encoding='utf-8') as f:
        file_data = json.load(f)
        file_data.pop(n)
        j = open(file_path, 'w+', encoding='utf-8')
        json.dump(file_data, j, indent=4, ensure_ascii=False)
        j.close()
        f.close()

