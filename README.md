# pve-autorepl
This script setup replication for VM which start on boot.

Этот скрипт ищет VM, которые стартуют автоматически, но не реплицируются. 
Если такие VM найдены, то скрипт:
* Отправляет письмо на email root пользователя
* Затем он настраивает репликацию для найденных VM
