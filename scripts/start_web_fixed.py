services:
  - type: web
    name: dailycheck-dashboard
    env: python
    region: oregon
    plan: free
    
    # ИЗМЕНЕННАЯ команда запуска - используем ИСПРАВЛЕННЫЙ файл
    buildCommand: |
      pip install --upgrade pip
      pip install -r requirements-web.txt
    
    startCommand: python scripts/start_web_fixed.py
    
    envVars:
      - key: PORT
        value: 10000
      - key: HOST  
        value: 0.0.0.0
      - key: ENVIRONMENT
        value: production
      - key: DEBUG
        value: false
    
    healthCheckPath: /health
    autoDeploy: true
    rootDir: ./
