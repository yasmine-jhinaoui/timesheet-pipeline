package tn.esprit.spring.services;

import java.util.List;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import tn.esprit.spring.entities.User;
import tn.esprit.spring.repository.UserRepository;

@Service
public class UserServiceImpl implements IUserService {

	@Autowired
	UserRepository userRepository;



	private static final Logger l = LogManager.getLogger(UserServiceImpl.class);

	@Override
	public List<User> retrieveAllUsers() {
         List<User> users = null;
          try {
           l.info("In retrieveAllUsers()");
           users = (List<User>) userRepository.findAll();
           l.info("Users retrieved successfully");
          } catch (Exception e) {
          l.error("Error in retrieveAllUsers() : " + e);
          }
         return users;
        }



	@Override
	public User addUser(User u) {

		User utilisateur = null; 

		try {
			// TODO Log à ajouter en début de la méthode 
			utilisateur = userRepository.save(u); 
			// TODO Log à ajouter à la fin de la méthode 

		} catch (Exception e) {
			// TODO log ici : l....("error in addUser() : " + e);
		}

		return utilisateur; 
	}

	@Override 
	public User updateUser(User u) {

		User userUpdated = null; 
		User u_saved = null; 

		
		try {
			// TODO Log à ajouter en début de la méthode 
			userUpdated = userRepository.save(u); 
			// TODO Log à ajouter à la fin de la méthode 

		} catch (Exception e) {
			// TODO log ici : l....("error in updateUser() : " + e);
		}

		return userUpdated; 
	}

	@Override
	public void deleteUser(String id) {

		try {
			// TODO Log à ajouter en début de la méthode 
			userRepository.deleteById(Long.parseLong(id)); 
			// TODO Log à ajouter à la fin de la méthode 

		} catch (Exception e) {
			// TODO log ici : l....("error in deleteUser() : " + e);
		}

	}

	@Override
public User retrieveUser(String id) {
    User u = null;
    try {
        Long userId = Long.parseLong(id);
        l.info("Recherche utilisateur avec ID: " + userId);
        java.util.Optional<User> optional = userRepository.findById(userId);
        if (optional.isPresent()) {
            u = optional.get();
            l.info("Utilisateur trouvé: " + u.getFirstName() + " " + u.getLastName());
        } else {
            l.warn("Aucun utilisateur trouvé avec ID: " + userId);
        }
    } catch (NumberFormatException e) {
        l.error("ID invalide (doit être un nombre): " + id + " - Erreur: " + e.getMessage());
    } catch (Exception e) {
        l.error("Erreur dans retrieveUser() pour ID: " + id + " - " + e.getMessage());
    }
    return u;
}

	
	
	
}
