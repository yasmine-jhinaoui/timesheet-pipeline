package tn.esprit.spring.services;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

import java.util.Arrays;
import java.util.List;
import java.util.Optional;

import org.junit.jupiter.api.MethodOrderer.OrderAnnotation;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import tn.esprit.spring.entities.User;
import tn.esprit.spring.repository.UserRepository;

@TestMethodOrder(OrderAnnotation.class)
@ExtendWith(MockitoExtension.class)
class UserServiceImplMockTest {

    @Mock
    UserRepository userRepository;

    @InjectMocks
    UserServiceImpl userService;

    @Test
    @Order(1)
    void retrieveAllUsers_returnsList() {
        List<User> users = Arrays.asList(new User(), new User());
        when(userRepository.findAll()).thenReturn(users);

        List<User> result = userService.retrieveAllUsers();

        assertEquals(2, result.size());
        verify(userRepository).findAll();
    }

    @Test
    @Order(2)
    void retrieveAllUsers_onError_returnsNull() {
        when(userRepository.findAll()).thenThrow(new RuntimeException("DB down"));

        assertNull(userService.retrieveAllUsers());
    }

    @Test
    @Order(3)
    void addUser_returnsSavedUser() {
        User u = new User();
        when(userRepository.save(u)).thenReturn(u);

        assertSame(u, userService.addUser(u));
        verify(userRepository).save(u);
    }

    @Test
    @Order(4)
    void updateUser_returnsUpdatedUser() {
        User u = new User();
        when(userRepository.save(u)).thenReturn(u);

        assertSame(u, userService.updateUser(u));
    }

    @Test
    @Order(5)
    void deleteUser_callsRepository() {
        userService.deleteUser("1");

        verify(userRepository).deleteById(1L);
    }

    @Test
    @Order(6)
    void retrieveUser_found() {
        User u = new User();
        when(userRepository.findById(1L)).thenReturn(Optional.of(u));

        assertSame(u, userService.retrieveUser("1"));
    }

    @Test
    @Order(7)
    void retrieveUser_notFound_returnsNull() {
        when(userRepository.findById(99L)).thenReturn(Optional.empty());

        assertNull(userService.retrieveUser("99"));
    }

    @Test
    @Order(8)
    void retrieveUser_invalidId_returnsNull() {
        assertNull(userService.retrieveUser("abc"));

        verifyNoInteractions(userRepository);
    }
}
