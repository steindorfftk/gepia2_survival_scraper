from bs4 import BeautifulSoup
import requests
from time import sleep
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import UnexpectedAlertPresentException
from selenium.common.exceptions import NoAlertPresentException
from selenium.common.exceptions import NoSuchElementException
from urllib.parse import urlparse, urljoin
import time

# Input file
quartile = ['BLCA','BRCA','HNSC','KIRC','LGG','LIHC','LUAD','LUSC','OV','PRAD','SKCM','STAD','THCA']
quartile = ['KIRC','LGG','LIHC','LUAD','LUSC','OV','PRAD','SKCM','STAD','THCA']
tercile = ['CESC','COAD','ESCA','GBM','KIRP','LAML','PAAD','PCPG','READ','SARC','TGCT','THYM','UCEC']
median = ['ACC','CHOL','DLBC','KICH','MESO','UCS','UVM']
datasets = []

for value in quartile:
	datasets.append(value)
	
#for value in tercile:
#	datasets.append(value)

#for value in median:
#	datasets.append(value)

genes = []

	
with open('genes.txt', 'r') as texto:
	for line in texto:
		linha = line.split()
		if len(linha) > 0:
			genes.append(linha[0])

def main():
	start_time = time.time()
	i = 0

	firefox_options = Options()
	firefox_options.add_argument('--headless')
	driver = webdriver.Firefox(options=firefox_options)
	driver.get('http://gepia2.cancer-pku.cn/#survival')

	for value in datasets:
		if value in quartile:
			high_cutoff = '67'
			low_cutoff = '33'
		elif value in tercile:
			high_cutoff = '67'
			low_cutoff = '33'
		elif value in median:
			high_cutoff = '50'
			low_cutoff = '50'
		csv_name = value + '.csv'
		if csv_name not in os.listdir():
			with open(csv_name,'w') as texto:
				texto.write('Gene , PValue , HR , Worse prognosis \n')
			remaining_genes = genes
		else:
			with open(csv_name,'r') as texto:
				done_genes = []
				for line in texto:
					if 'Gene' not in line:
						linha = line.split()
						if '"' in linha[0]:
							done_genes.append(linha[0][1:])
						else:
							done_genes.append(linha[0])
			remaining_genes = [value for value in genes if value not in done_genes]
		sleep(10)
		print(len(remaining_genes))
		with open(csv_name,'a') as texto:
			retry_count = 0
			retry = False
			for gene in remaining_genes:
				print(f'Retry count: {retry_count}')
				print(f'Retry: {retry}')
				error = False
				if retry == True:
					print('Restarting...')
					driver.close()
					main()
				try:
		    
				    # Wait for the button to be present
				    button = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, "//button[@id='survival_plot']")))

				    # Set values for survival_signature and survival_dataset
				    script_a = f"document.getElementById('survival_signature').value='{gene}';"
				    driver.execute_script(script_a)
				    script_b = f"document.getElementById('survival_dataset').value='{value}';"
				    driver.execute_script(script_b)

				    # Set values for survival_groupcutoff1 and survival_groupcutoff2
				    script_c = f"document.getElementById('survival_groupcutoff1').value='{high_cutoff}';"
				    driver.execute_script(script_c)
				    script_d = f"document.getElementById('survival_groupcutoff2').value='{low_cutoff}';"
				    driver.execute_script(script_d)
				    sleep(4)

				    # Click on the button
				    driver.execute_script("arguments[0].click();", button)

				    # Wait for the page to load
				    sleep(2)
				    iframe_element = driver.find_element(By.ID, "iframe")
				    driver.switch_to.frame(iframe_element)
				    span_element_a = driver.find_element(By.XPATH, "//span[contains(text(),'Logrank')]")
				    span_text_a = span_element_a.text
				    texto.write(gene + ' , ')
				    texto.write(span_text_a[10:] + ' , ')
				    span_element_b = driver.find_element(By.XPATH, "//span[contains(text(),'HR(high)')]")
				    span_text_b = span_element_b.text
					    
				    texto.write(span_text_b[9:] + ' , ')
				    driver.switch_to.default_content()
				    if 'e' in span_text_a[10:]:
				    	if 'e' in span_text_b[9:]:
				    		texto.write('Low \n')
				    	else:
					    	if float(span_text_b[9:]) >= 1:
					    		texto.write('High \n')
					    	else:
					    		texto.write('Low \n')
				    else:
					    if float(span_text_a[10:]) <= 0.05:
					    	if 'e' in span_text_b[9:]:
					    		texto.write('Low \n')
					    	else:
					    		if float(span_text_b[9:]) >= 1:
					    			texto.write('High \n')
					    		else:
					    			texto.write('Low \n')
					    else:
					    	texto.write('NA \n') 
					    
				except UnexpectedAlertPresentException:
					try:
						driver.switch_to.alert.dismiss()
					except NoAlertPresentException:
						texto.write(gene + ' , NA , NA , NA \n')
						pass
#					print(NoAlertPresentException)
					print(f'{gene} not available for {value}')
					error = True
				except TimeoutException:
#					print(TimeoutException)
					print(f'Time out {gene} for {value}')
					error = True
					retry_count += 1
					pass
				except NoSuchElementException:
#					print(NoSuchElementException)
					print(f'Time out {gene} for {value}')
					error = True
					retry_count += 1
				finally:
				    if retry_count == 3:
				    	retry = True
				    texto.flush()
				end_time = time.time()
				i += 1
				elapsed_time = end_time - start_time
				mean_time = round(elapsed_time/i, 2)
				if error == False:
					print(f'Done ({gene} for {value}) [{mean_time} seconds/gene]')    
	driver.close()				
				

main()


