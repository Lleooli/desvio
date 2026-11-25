/**
 * As distâncias entre paradas que o app oferece, na Nova viagem e no Perfil (canvas
 * NovaViagem e Perfil). O coletor aceita de 10 a 600 km.
 */

/** O padrão enquanto a pessoa não escolhe um no perfil. */
export const INTERVALO_PADRAO = 200;

export const INTERVALOS = [150, 200, 300].map((km) => ({ valor: km, label: `${km} km` }));
