-- Script de inicialización de la base de datos LTC
-- Este archivo se ejecuta automáticamente al crear el contenedor PostgreSQL

-- Crear extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Tabla de candidatos
CREATE TABLE IF NOT EXISTS candidatos (
    id SERIAL PRIMARY KEY,
    usuario_id UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    nombre VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE,
    telefono VARCHAR(50),
    ciudad VARCHAR(100),
    pais VARCHAR(100),
    titulo_profesional VARCHAR(255),
    resumen_profesional TEXT,
    cv_filename VARCHAR(255),
    cv_processed BOOLEAN DEFAULT FALSE,
    habilidades JSONB,
    experiencias JSONB,
    educaciones JSONB,
    certificaciones JSONB,
    idiomas JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de vacantes
CREATE TABLE IF NOT EXISTS vacantes (
    id SERIAL PRIMARY KEY,
    titulo VARCHAR(255) NOT NULL,
    empresa VARCHAR(255),
    empresa_nombre VARCHAR(255),
    ubicacion VARCHAR(255),
    modalidad VARCHAR(100),
    tipo_empleo VARCHAR(100),
    salario DECIMAL(10,2),
    salario_min DECIMAL(10,2),
    salario_max DECIMAL(10,2),
    nivel_experiencia VARCHAR(100),
    descripcion TEXT,
    requisitos JSONB,
    habilidades_requeridas JSONB,
    activa BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de matches (opcional, para tracking)
CREATE TABLE IF NOT EXISTS matches (
    id SERIAL PRIMARY KEY,
    candidato_id UUID REFERENCES candidatos(usuario_id),
    vacante_id INTEGER REFERENCES vacantes(id),
    score DECIMAL(5,2),
    analisis JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para mejorar rendimiento
CREATE INDEX IF NOT EXISTS idx_candidatos_usuario_id ON candidatos(usuario_id);
CREATE INDEX IF NOT EXISTS idx_candidatos_email ON candidatos(email);
CREATE INDEX IF NOT EXISTS idx_vacantes_activa ON vacantes(activa);
CREATE INDEX IF NOT EXISTS idx_vacantes_empresa ON vacantes(empresa);
CREATE INDEX IF NOT EXISTS idx_matches_candidato ON matches(candidato_id);
CREATE INDEX IF NOT EXISTS idx_matches_vacante ON matches(vacante_id);
CREATE INDEX IF NOT EXISTS idx_matches_score ON matches(score);

-- Datos de ejemplo para vacantes
INSERT INTO vacantes (titulo, empresa, ubicacion, modalidad, salario_min, salario_max, nivel_experiencia, descripcion, requisitos, habilidades_requeridas) VALUES
('Desarrollador Python Senior', 'TechCorp', 'Madrid, España', 'Híbrido', 45000, 65000, 'Senior', 'Buscamos un desarrollador Python senior para unirse a nuestro equipo de desarrollo de aplicaciones web y APIs.', '["5+ años de experiencia en Python", "Experiencia con Django/Flask", "Conocimientos de bases de datos", "Git y metodologías ágiles"]', '["Python", "Django", "Flask", "PostgreSQL", "Git", "Docker"]'),
('Desarrollador Frontend React', 'StartupXYZ', 'Barcelona, España', 'Remoto', 35000, 50000, 'Mid-Senior', 'Desarrollador frontend especializado en React para crear interfaces de usuario modernas y responsivas.', '["3+ años de experiencia en React", "Conocimientos de TypeScript", "Experiencia con APIs REST", "Metodologías ágiles"]', '["React", "TypeScript", "JavaScript", "HTML", "CSS", "Git"]'),
('Ingeniero DevOps', 'CloudTech', 'Valencia, España', 'Presencial', 50000, 70000, 'Senior', 'Ingeniero DevOps para gestionar infraestructura cloud y automatizar procesos de CI/CD.', '["5+ años en DevOps", "Experiencia con AWS/Azure", "Docker y Kubernetes", "Jenkins/GitLab CI"]', '["AWS", "Docker", "Kubernetes", "Jenkins", "Terraform", "Linux"]'),
('Analista de Datos', 'DataCorp', 'Sevilla, España', 'Híbrido', 30000, 45000, 'Mid', 'Analista de datos para extraer insights de grandes volúmenes de información y crear reportes.', '["3+ años en análisis de datos", "SQL avanzado", "Python para análisis", "Herramientas de visualización"]', '["Python", "SQL", "Pandas", "Matplotlib", "Power BI", "Excel"]'),
('Desarrollador Full Stack', 'DigitalAgency', 'Bilbao, España', 'Remoto', 40000, 60000, 'Senior', 'Desarrollador full stack para crear aplicaciones web completas desde frontend hasta backend.', '["5+ años de experiencia full stack", "JavaScript/TypeScript", "Node.js", "React/Vue", "Bases de datos"]', '["JavaScript", "Node.js", "React", "PostgreSQL", "MongoDB", "Docker"]')
ON CONFLICT DO NOTHING;

-- Función para actualizar timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers para actualizar timestamps
CREATE TRIGGER update_candidatos_updated_at BEFORE UPDATE ON candidatos FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_vacantes_updated_at BEFORE UPDATE ON vacantes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Comentarios para documentación
COMMENT ON TABLE candidatos IS 'Tabla principal de candidatos con información de CVs procesados';
COMMENT ON TABLE vacantes IS 'Tabla de vacantes de empleo disponibles';
COMMENT ON TABLE matches IS 'Tabla de matches entre candidatos y vacantes'; 